# -*- coding: utf-8 -*-
"""Parameter-hallucination detection by value provenance.

An argument value counts as GROUNDED if it (as a string) appears in any of:
  1. the task instruction,
  2. the system prompt (contains sandbox today's date),
  3. tool results returned so far in this trajectory,
  4. the closed sandbox world (data/world.json serialization),
  5. small integers 0..100 (counts/quantities),
  6. an arithmetic expression whose numbers are all grounded (calculate).
Anything else (invented ids, cities, prices, dates outside the world)
is a hallucinated value. Deterministic, no LLM involved.
"""
from __future__ import annotations

import json
import re
from typing import Any

from .. import config

_NUM_IN_EXPR = re.compile(r"\d+(?:\.\d+)?")


class ProvenanceIndex:
    def __init__(self, task: dict, world_text: str | None = None):
        self.instruction = task["instruction"].casefold()
        self.world_text = (world_text if world_text is not None
                           else config.WORLD_PATH.read_text(encoding="utf-8")).casefold()
        self.system_text = ""
        self.results_text = ""

    def add_system(self, text: str) -> None:
        self.system_text += text.casefold()

    def add_result(self, payload: Any) -> None:
        self.results_text += json.dumps(payload, ensure_ascii=False).casefold()

    def _grounded_scalar(self, s: str) -> bool:
        v = s.strip().strip('"').casefold()
        if not v:
            return True
        if v in ("true", "false", "null", "none"):
            return True
        # small integers are generic quantities, not claims about the world
        try:
            f = float(v)
            if f == int(f) and 0 <= int(f) <= 100:
                return True
        except ValueError:
            pass
        if len(v) >= 2 and v in self.instruction:
            return True
        if len(v) >= 2 and v in self.system_text:
            return True
        if len(v) >= 2 and v in self.results_text:
            return True
        if len(v) >= 2 and v in self.world_text:
            return True
        return False

    def is_grounded(self, value: Any, tool: str = "", arg: str = "") -> bool:
        if value is None or isinstance(value, bool):
            return True
        if isinstance(value, (int, float)):
            return self._grounded_scalar(str(value))
        if isinstance(value, list):
            return all(self.is_grounded(v, tool, arg) for v in value)
        if isinstance(value, dict):
            return all(self.is_grounded(v, tool, arg) for v in value.values())
        s = str(value)
        if tool == "calculate" and arg == "expression":
            nums = _NUM_IN_EXPR.findall(s)
            return all(self._grounded_scalar(n) or float(n) <= 100 for n in nums) \
                if nums else True
        # unparseable args blob is by definition not grounded
        if "_unparseable" in s or "_non_object" in s:
            return False
        return self._grounded_scalar(s)


def scan_call(idx: ProvenanceIndex, call: dict) -> list[dict]:
    """Return list of hallucinated {tool, arg, value} for one call."""
    out = []
    args = call.get("args") or {}
    for k, v in args.items():
        if k in ("_unparseable", "_non_object"):
            out.append({"tool": call.get("tool"), "arg": k, "value": str(v)[:120]})
            continue
        if not idx.is_grounded(v, call.get("tool", ""), k):
            out.append({"tool": call.get("tool"), "arg": k, "value": str(v)[:120]})
    return out


def scan_trajectory(task: dict, calls: list[dict]) -> list[dict]:
    """Walk calls in order, feeding results into the provenance index
    exactly as the model saw them."""
    idx = ProvenanceIndex(task)
    idx.add_system(config.TODAY)  # system prompt grounds the sandbox date
    findings: list[dict] = []
    for c in calls:
        for f in scan_call(idx, c):
            f["seq"] = c.get("seq")
            findings.append(f)
        idx.add_result(c.get("result"))
    return findings
