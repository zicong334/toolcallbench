# -*- coding: utf-8 -*-
"""Failure gallery: extract and classify interesting failed trajectories."""
from __future__ import annotations

import json
from pathlib import Path


FAILURE_TYPES = ("hallucinated_param", "wrong_tool", "wrong_params",
                 "no_recovery", "wrong_final_answer", "schema_violation",
                 "incomplete")


def classify(g: dict) -> list[str]:
    tags = []
    if g["n_hallucinated_args"]:
        tags.append("hallucinated_param")
    if g["tool_selection_rate"] < 1.0:
        tags.append("wrong_tool")
    elif g["param_accuracy"] < 1.0:
        tags.append("wrong_params")
    if g["recovery"].get("applicable") and not g["recovery"]["ok"]:
        tags.append("no_recovery")
    if not g["final_answer_ok"]:
        tags.append("wrong_final_answer")
    if g["schema_violations"]:
        tags.append("schema_violation")
    if g["status"] != "completed":
        tags.append("incomplete")
    return tags or ["unknown"]


def _condensed_traj(traj: dict, max_calls: int = 8) -> str:
    lines = [f"> 指令: {traj.get('instruction', '')[:160]}"]
    for c in (traj.get("calls") or [])[:max_calls]:
        args = json.dumps(c.get("args"), ensure_ascii=False)
        if len(args) > 160:
            args = args[:160] + "…"
        mark = "✔" if c.get("ok") else f"✘ {c.get('error_code') or ''}{' (injected)' if c.get('injected') else ''}"
        lines.append(f"> `{c['tool']}({args})` → {mark}")
    fin = (traj.get("final_content") or "<无终答>")
    if len(fin) > 300:
        fin = fin[:300] + "…"
    lines.append(f"> 终答: {fin}")
    return "\n".join(lines)


def build_gallery_md(grades: list[dict], traj_dir: Path, limit: int = 14) -> str:
    fails = [g for g in grades if not g["task_pass"]]
    # prefer diverse (model, failure type) coverage
    seen: set[tuple[str, str]] = set()
    picked = []
    for g in sorted(fails, key=lambda x: -x["n_hallucinated_args"]):
        tags = classify(g)
        key = (g["model_id"] or g["model"], tags[0])
        if key not in seen or len(picked) < limit // 2:
            seen.add(key)
            picked.append((g, tags))
        if len(picked) >= limit:
            break

    out = ["# 失败案例图鉴(Failure Gallery)", "",
           f"共 {len(fails)} 个未通过单元,摘录 {len(picked)} 例,按失败类型归类。", ""]
    for g, tags in picked:
        model = g["model_id"] or g["model"]
        fp = Path(traj_dir) / model / f"{g['task_id']}__r{g['run_idx']}.json"
        out.append(f"## {g['task_id']} · {model} · {', '.join(tags)}")
        if fp.exists():
            traj = json.loads(fp.read_text(encoding="utf-8"))
            out.append("")
            out.append(_condensed_traj(traj))
            if g["hallucinations"]:
                h = g["hallucinations"][:3]
                out.append("")
                out.append("幻觉参数: " + "; ".join(
                    f"`{x['tool']}.{x['arg']}={x['value']}`" for x in h))
            if g["final_answer_missing"]:
                out.append(f"缺失事实: {g['final_answer_missing']}")
            if g["final_answer_banned"]:
                out.append(f"触犯禁语: {g['final_answer_banned']}")
        else:
            out.append(f"(轨迹文件缺失: {fp})")
        out.append("")
    return "\n".join(out) + "\n"
