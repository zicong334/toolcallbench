# -*- coding: utf-8 -*-
"""Task loading + strict schema validation. Every task must pass before eval."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from .. import config
from ..sandbox.tools import TOOL_NAMES

DOMAINS = {"weather", "schedule", "orders", "ledger", "travel", "fault"}
LANGS = {"zh", "en"}
MATCHER_KINDS = {"equals", "numeric", "in_set", "regex", "contains", "any"}
ID_RE = re.compile(r"^[WSOLTF]-\d{3}$")


class TaskError(ValueError):
    pass


def _check_matcher(spec, ctx: str) -> None:
    if not isinstance(spec, dict) or len(spec) != 1:
        raise TaskError(f"{ctx}: matcher must be a single-key dict, got {spec!r}")
    kind, val = next(iter(spec.items()))
    if kind not in MATCHER_KINDS:
        raise TaskError(f"{ctx}: unknown matcher {kind!r}")
    if kind == "equals" and not isinstance(val, (str, int, float, bool)):
        raise TaskError(f"{ctx}: equals needs scalar")
    if kind == "numeric":
        if not isinstance(val, dict) or "value" not in val:
            raise TaskError(f"{ctx}: numeric needs {{value, tol}}")
    if kind == "in_set" and (not isinstance(val, list) or not val):
        raise TaskError(f"{ctx}: in_set needs non-empty list")
    if kind == "regex" and not isinstance(val, str):
        raise TaskError(f"{ctx}: regex needs str")


def validate_task(t: dict, fname: str) -> None:
    ctx = fname
    for field in ("id", "domain", "lang", "instruction", "tools", "max_turns", "grading"):
        if field not in t:
            raise TaskError(f"{ctx}: missing field {field!r}")
    if not ID_RE.match(t["id"]):
        raise TaskError(f"{ctx}: bad id {t['id']!r} (need [WSOLTF]-NNN)")
    if t["domain"] not in DOMAINS:
        raise TaskError(f"{ctx}: bad domain {t['domain']!r}")
    if t["lang"] not in LANGS:
        raise TaskError(f"{ctx}: bad lang {t['lang']!r}")
    if not isinstance(t["instruction"], str) or len(t["instruction"]) < 10:
        raise TaskError(f"{ctx}: instruction too short")
    if not isinstance(t["tools"], list) or not t["tools"]:
        raise TaskError(f"{ctx}: tools must be non-empty list")
    bad = [x for x in t["tools"] if x not in TOOL_NAMES]
    if bad:
        raise TaskError(f"{ctx}: unknown tools {bad}")
    if not isinstance(t["max_turns"], int) or not (2 <= t["max_turns"] <= 16):
        raise TaskError(f"{ctx}: max_turns must be int 2..16")

    for i, f in enumerate(t.get("faults") or []):
        if f.get("tool") not in t["tools"]:
            raise TaskError(f"{ctx}: faults[{i}] tool not in task tools")
        if f.get("mode") not in ("fail_n_times", "always", "invalid_on"):
            raise TaskError(f"{ctx}: faults[{i}] bad mode")

    g = t["grading"]
    if not isinstance(g, dict):
        raise TaskError(f"{ctx}: grading must be dict")
    req = g.get("required_calls") or []
    if not isinstance(req, list):
        raise TaskError(f"{ctx}: required_calls must be list")

    def _check_call(call: dict, cctx: str) -> None:
        if call.get("tool") not in TOOL_NAMES:
            raise TaskError(f"{cctx} bad tool {call.get('tool')!r}")
        if call.get("tool") not in t["tools"]:
            raise TaskError(f"{cctx} tool not exposed in task tools")
        for k, m in (call.get("args") or {}).items():
            _check_matcher(m, f"{cctx} args.{k}")

    for i, call in enumerate(req):
        if isinstance(call, dict) and "any_of" in call:
            alts = call["any_of"]
            if not isinstance(alts, list) or len(alts) < 2:
                raise TaskError(f"{ctx}: required_calls[{i}].any_of needs >=2 alternatives")
            for j, alt in enumerate(alts):
                _check_call(alt, f"{ctx}: required_calls[{i}].any_of[{j}]")
        else:
            _check_call(call, f"{ctx}: required_calls[{i}]")
    for fn in g.get("forbidden_calls") or []:
        if fn not in TOOL_NAMES:
            raise TaskError(f"{ctx}: forbidden_calls bad tool {fn!r}")
    fa = g.get("final_answer") or {}
    for key in ("must_include", "must_not_include"):
        v = fa.get(key)
        if v is not None and (not isinstance(v, list)
                              or not all(isinstance(x, str) for x in v)):
            raise TaskError(f"{ctx}: final_answer.{key} must be list[str]")
    if t["domain"] == "fault" and not t.get("faults"):
        raise TaskError(f"{ctx}: fault-domain task without faults config")
    if t.get("faults") and not g.get("expect_recovery") and not g.get("allow_honest_failure"):
        raise TaskError(f"{ctx}: fault task needs expect_recovery or allow_honest_failure")


def load_tasks(tasks_dir: Path | None = None) -> list[dict]:
    tasks_dir = Path(tasks_dir or config.TASKS_DIR)
    files = sorted(tasks_dir.rglob("*.yaml"))
    if not files:
        raise TaskError(f"no task yaml under {tasks_dir}")
    seen: dict[str, str] = {}
    out = []
    for fp in files:
        t = yaml.safe_load(fp.read_text(encoding="utf-8"))
        validate_task(t, fp.name)
        if t["id"] in seen:
            raise TaskError(f"duplicate id {t['id']} in {fp.name} and {seen[t['id']]}")
        seen[t["id"]] = fp.name
        t["_file"] = str(fp)
        out.append(t)
    return out
