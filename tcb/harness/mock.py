# -*- coding: utf-8 -*-
"""Mock providers for offline E2E tests and zero-API fallback runs.

OracleMock   : replays the gold trajectory implied by grading.required_calls,
               then emits a final message containing every must_include value.
               On a correct benchmark, OracleMock must pass every task.
ChaoticMock  : deliberately misbehaves (wrong tool, hallucinated arg values,
               ignores faults, fabricates success) so graders get exercised
               on negative cases.
"""
from __future__ import annotations

import json
import random
from typing import Any


def _expand_required(task: dict) -> list[dict]:
    out = []
    for call in (task["grading"].get("required_calls") or []):
        if "any_of" in call:
            call = call["any_of"][0]
        args = {}
        for k, m in (call.get("args") or {}).items():
            kind, val = next(iter(m.items()))
            if kind in ("equals", "contains", "regex"):
                args[k] = val
            elif kind == "in_set":
                args[k] = val[0]
            elif kind == "numeric":
                args[k] = val["value"]
            else:  # any
                args[k] = "1"
        out.append({"tool": call["tool"], "args": args})
    return out


class OracleMock:
    name = "mock-oracle"

    def __init__(self, task: dict):
        self.task = task
        self.plan = _expand_required(task)
        self.step = 0
        self._retries = 0
        self._max_retries = 4

    def _last_tool_result_injected(self, messages: list[dict]) -> bool:
        for m in reversed(messages):
            if m.get("role") == "tool":
                return '"injected": true' in (m.get("content") or "")
        return False

    def _emit(self, call: dict, tools: list[dict]) -> dict[str, Any]:
        args = dict(call["args"])
        spec = next((t for t in tools if t["function"]["name"] == call["tool"]), None)
        if spec:
            required = spec["function"]["parameters"].get("required", [])
            for r in required:
                if r not in args:
                    args[r] = ("2026-10-27" if r in ("date", "checkin")
                               else "ACC001" if r == "account_id"
                               else "1" if r in ("quantity", "passengers",
                                                 "nights", "rooms", "days",
                                                 "duration_min")
                               else "1")
        self.step += 1
        return {"role": "assistant", "content": None,
                "tool_calls": [{"id": f"mock_{self.step}", "name": call["tool"],
                                "arguments": args,
                                "raw_arguments": json.dumps(args, ensure_ascii=False)}],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0}}

    def complete(self, messages: list[dict], tools: list[dict],
                 task_id: str = "") -> dict[str, Any]:
        # retry-on-injected-fault: replay the same step until it stops failing
        if (self.step > 0 and self._retries < self._max_retries
                and self._last_tool_result_injected(messages)):
            self._retries += 1
            self.step -= 1
            out = self._emit(self.plan[self.step], tools)
            return out
        self._retries = 0
        if self.step < len(self.plan):
            return self._emit(self.plan[self.step], tools)
        fa = self.task["grading"].get("final_answer") or {}
        parts = ["已完成。"] + [str(v) for v in (fa.get("must_include") or [])]
        return {"role": "assistant", "content": " ".join(parts), "tool_calls": [],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0}}


class ChaoticMock:
    """Fails in characteristic ways; graders must catch every one."""
    name = "mock-chaos"

    def __init__(self, task: dict, seed: int = 0):
        self.task = task
        self.rng = random.Random(seed)
        self.step = 0

    def complete(self, messages: list[dict], tools: list[dict],
                 task_id: str = "") -> dict[str, Any]:
        self.step += 1
        names = [t["function"]["name"] for t in tools]
        gold_tools = {c["tool"] for c in _expand_required(self.task)}
        distractors = [n for n in names if n not in gold_tools]
        if self.step == 1 and distractors:
            # wrong tool first
            name = distractors[0]
            args = {"city": "亚特兰蒂斯", "date": "1999-01-01", "query": "不存在",
                    "expression": "1+1", "account_id": "ACC999",
                    "product_id": "P9999", "origin": "火星", "dest": "月球",
                    "flight_id": "FL9999", "hotel_id": "HT999",
                    "event_id": "E999", "order_id": "O9999",
                    "title": "x", "start_time": "10:00", "duration_min": 30,
                    "quantity": 1, "address_id": "A9", "checkin": "2026-10-29",
                    "nights": 1, "rooms": 1, "passengers": 1, "category": "电子产品",
                    "days": 3, "month": "2026-10"}
            spec = next(t for t in tools if t["function"]["name"] == name)
            keep = {k: v for k, v in args.items()
                    if k in spec["function"]["parameters"]["properties"]}
            return {"role": "assistant", "content": None,
                    "tool_calls": [{"id": f"chaos_{self.step}", "name": name,
                                    "arguments": keep,
                                    "raw_arguments": json.dumps(keep, ensure_ascii=False)}],
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0}}
        # then fabricate a confident success without doing the work
        return {"role": "assistant",
                "content": "已完成。预订成功,订单号 O6001,一切都已确认无误,没有任何冲突。",
                "tool_calls": [],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0}}
