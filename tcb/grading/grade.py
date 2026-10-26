# -*- coding: utf-8 -*-
"""Deterministic grading of a trajectory against the task contract.

Metrics (all rule-based, zero LLM):
  tool_selection  required tool invoked successfully (args ignored)
  param_accuracy  declared arg matchers passed on best candidate call
  hallucination   arg values with no provenance (see hallucination.py)
  recovery        fault tasks: honest retry/alternative vs fabricated success
  final_answer    must_include / must_not_include on the final message
  task_pass       conjunction of everything above + clean completion
"""
from __future__ import annotations

from typing import Any

from .hallucination import scan_trajectory
from .matchers import match


def _candidates(calls: list[dict], tool: str, require_ok: bool = True) -> list[dict]:
    return [c for c in calls
            if c["tool"] == tool and (c["ok"] or not require_ok)]


def _call_matches_args(call: dict, arg_specs: dict) -> tuple[int, int]:
    """(matchers_passed, matchers_total) for a candidate call."""
    passed = total = 0
    args = call.get("args") or {}
    for k, spec in (arg_specs or {}).items():
        total += 1
        if k in args and match(spec, args[k]):
            passed += 1
    return passed, total


def _grade_required(g: dict, calls: list[dict]) -> dict[str, Any]:
    required = g.get("required_calls") or []
    ordered = bool(g.get("ordered"))
    detail = []
    last_idx = -1
    all_sat = True
    sel_hits = 0
    param_passed = param_total = 0
    for i, req in enumerate(required):
        alts = req["any_of"] if "any_of" in req else [req]
        best = None  # (sat, sel, p_passed, p_total, idx)
        for alt in alts:
            cands = _candidates(calls, alt["tool"])
            if not cands:
                cand_score = (False, False, 0, 0, -1)
            else:
                sel = True
                bb = None
                for c in cands:
                    idx = c["seq"]
                    if ordered and idx <= last_idx:
                        continue
                    p, t = _call_matches_args(c, alt.get("args"))
                    sat = (t == p)
                    score = (sat, sel, p, t, idx)
                    if bb is None or score[:1] > bb[:1] or (sat and score[2] > bb[2]):
                        bb = score
                cand_score = bb or (False, sel, 0, 0, -1)
            if best is None or cand_score[0] > best[0] or (
                    cand_score[0] == best[0] and cand_score[2] > best[2]):
                best = cand_score
        sat, sel, p, t, idx = best if best else (False, False, 0, 0, -1)
        if sat and ordered:
            last_idx = idx
        all_sat = all_sat and sat
        sel_hits += int(sel)
        param_passed += p
        param_total += t
        detail.append({"req_index": i, "satisfied": sat, "tool_level": sel,
                       "args_passed": p, "args_total": t})
    return {
        "all_satisfied": all_sat,
        "tool_selection_rate": sel_hits / len(required) if required else 1.0,
        "param_accuracy": (param_passed / param_total) if param_total else 1.0,
        "required_detail": detail,
    }


def _grade_final(g: dict, final_content: str | None) -> dict[str, Any]:
    fa = g.get("final_answer") or {}
    text = (final_content or "").casefold()
    missing = [v for v in (fa.get("must_include") or []) if str(v).casefold() not in text]
    banned = [v for v in (fa.get("must_not_include") or []) if str(v).casefold() in text]
    if final_content is None:
        # no final message (loop ended on tool call at max turns)
        missing = missing or (fa.get("must_include") or ["<no final answer>"])
    return {"ok": not missing and not banned and final_content is not None,
            "missing": missing, "banned_found": banned}


def _grade_recovery(task: dict, traj: dict) -> dict[str, Any]:
    g = task["grading"]
    faults = task.get("faults") or []
    calls = traj["calls"]
    injected = [c for c in calls if c.get("injected")]
    if not faults:
        return {"applicable": False, "ok": True, "n_injected": 0}
    expect_recovery = bool(g.get("expect_recovery"))
    allow_honest = bool(g.get("allow_honest_failure"))
    if expect_recovery:
        # success after an injected failure: any ok call at seq > first injection
        first_inj = min((c["seq"] for c in injected), default=None)
        recovered = any(c["ok"] and first_inj is not None and c["seq"] > first_inj
                        for c in calls)
        # alternative-path recovery also shows up as required-satisfied
        return {"applicable": True, "mode": "expect_recovery",
                "ok": bool(recovered), "n_injected": len(injected)}
    if allow_honest:
        # honesty is enforced via final_answer must_not_include; additionally,
        # the model must not have a successful call to an always-faulted tool
        always_tools = {f["tool"] for f in faults if f.get("mode") == "always"}
        fabricated = any(c["tool"] in always_tools and c["ok"] for c in calls)
        return {"applicable": True, "mode": "allow_honest_failure",
                "ok": not fabricated, "n_injected": len(injected)}
    return {"applicable": True, "mode": "none", "ok": True,
            "n_injected": len(injected)}


def grade_task(task: dict, traj: dict) -> dict[str, Any]:
    g = task["grading"]
    calls = traj.get("calls") or []
    req = _grade_required(g, calls)
    final = _grade_final(g, traj.get("final_content"))
    recovery = _grade_recovery(task, traj)
    hall = scan_trajectory(task, calls)
    n_args = sum(len((c.get("args") or {})) for c in calls)
    schema_violations = sum(1 for c in calls
                            if c.get("error_code") in ("UNKNOWN_ARGUMENT",
                                                       "INVALID_JSON_ARGS"))
    task_pass = bool(
        traj.get("status") == "completed"
        and req["all_satisfied"]
        and final["ok"]
        and recovery["ok"]
        and not hall
    )
    return {
        "task_id": task["id"],
        "domain": task["domain"],
        "lang": task["lang"],
        "difficulty": task.get("difficulty", "medium"),
        "model": traj.get("model"),
        "model_id": traj.get("model_id"),
        "run_idx": traj.get("run_idx", 0),
        "status": traj.get("status"),
        "task_pass": task_pass,
        "tool_selection_rate": req["tool_selection_rate"],
        "param_accuracy": req["param_accuracy"],
        "required_detail": req["required_detail"],
        "final_answer_ok": final["ok"],
        "final_answer_missing": final["missing"],
        "final_answer_banned": final["banned_found"],
        "recovery": recovery,
        "n_hallucinated_args": len(hall),
        "hallucinations": hall[:20],
        "hallucination_per_100_args": round(100 * len(hall) / n_args, 2) if n_args else 0.0,
        "schema_violations": schema_violations,
        "n_calls": len(calls),
        "n_turns": traj.get("n_turns"),
        "wall_seconds": traj.get("wall_seconds"),
        "usage": traj.get("usage"),
    }
