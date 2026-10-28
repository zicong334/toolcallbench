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
_HHMM = re.compile(r"^\d{1,2}:\d{2}$")


def _free_text_tokens(s: str) -> set[str]:
    """Word + CJK bigram tokens for soft grounding of free-text values."""
    toks = {w.lower() for w in re.findall(r"[A-Za-z]+", s)}
    cjk = re.findall(r"[一-鿿]", s)
    toks.update(a + b for a, b in zip(cjk, cjk[1:]))
    return toks


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

    def _soft_grounded(self, s: str) -> bool:
        """Token-level grounding for long free-text (titles, phrases).

        IDs/cities/dates are short and matched exactly; longer digit-free
        strings (e.g. event titles the model may rephrase) pass when most of
        their tokens come from allowed sources."""
        toks = _free_text_tokens(s)
        if not toks:
            return True
        hit = sum(1 for t in toks
                  if len(t) >= 2 and (t in self.instruction or t in self.results_text
                                      or t in self.world_text or t in self.system_text))
        return hit / len(toks) >= 0.6

    def _number_grounded(self, n: str) -> bool:
        """Numeric tokens need STRICT grounding: small generic quantities pass,
        anything else must literally occur in an allowed source. This is what
        keeps fabricated totals/ids from being laundered through soft matching."""
        try:
            f = float(n)
            if f == int(f) and 0 <= int(f) <= 100:
                return True
        except ValueError:
            pass
        return any(n in src for src in (self.instruction, self.system_text,
                                        self.results_text, self.world_text))

    def _grounded_scalar(self, s: str) -> bool:
        v = s.strip().strip('"').casefold()
        if not v:
            return True
        if v in ("true", "false", "null", "none"):
            return True
        # HH:MM clock values are derivable by arithmetic on world facts
        # (start + duration); correctness is enforced by arg matchers instead.
        if _HHMM.match(v):
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
        # Pure-CJK values are morphemic, not incidental noise: "米" is a
        # legitimate narrowing of the grounded "大米5kg" / instruction "大米".
        # (The len>=2 guard above exists to stop single latin chars/digits from
        # matching everywhere; that concern does not apply to CJK words.)
        if all("一" <= ch <= "鿿" for ch in v) and any(
                v in src for src in (self.instruction, self.system_text,
                                     self.results_text, self.world_text)):
            return True
        # Values mixing digits with text (e.g. "B5 笔记本", a reordering of the
        # grounded instruction "b5 notebook" + result field "笔记本B5"):
        # every numeric token must be STRICTLY grounded, the remaining text goes
        # through soft token grounding. Digits never get the soft pass.
        nums = _NUM_IN_EXPR.findall(v)
        if nums:
            if not all(self._number_grounded(n) for n in nums):
                return False
            rest = _NUM_IN_EXPR.sub(" ", v)
            # Only a text-bearing remainder earns soft grounding. A date like
            # "2026-12-25" leaves mere separators, and each of its numbers can
            # look innocuous alone (2026 occurs in the instruction, 12/25 are
            # small ints) — such structured values must match a source exactly,
            # which the substring checks above already tried.
            if _free_text_tokens(rest):
                return self._soft_grounded(rest)
            return False
        # long digit-free free text: allow faithful rephrasing
        if len(v) > 4:
            return self._soft_grounded(v)
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
    """Return list of hallucinated {tool, arg, value} for one call.

    calculate.expression is exempt: arithmetic intermediates (partial sums
    the model derived itself) are reasoning, not claims about the world.
    The final-answer check still verifies the reported result.
    """
    out = []
    args = call.get("args") or {}
    for k, v in args.items():
        if call.get("tool") == "calculate" and k == "expression":
            continue
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
