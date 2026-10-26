# -*- coding: utf-8 -*-
"""Per-task fault injection wrappers around sandbox dispatch.

Modes:
  fail_n_times : first N calls to the tool fail with the configured error
  always       : every call fails (e.g. deprecated service)
  invalid_on   : fails only when args match `match_args` exactly (subset match)

Injected errors carry "injected": true so graders/report can tell them apart
from genuine sandbox errors. Counters are per task run (fresh injector).
"""
from __future__ import annotations

from typing import Any

from .tools import dispatch as real_dispatch
from .world import WorldState


class FaultInjector:
    def __init__(self, fault_cfgs: list[dict]):
        self.cfgs = fault_cfgs or []
        self._counts: dict[str, int] = {}
        for c in self.cfgs:
            if c.get("mode") not in ("fail_n_times", "always", "invalid_on"):
                raise ValueError(f"bad fault mode: {c.get('mode')}")
            if c.get("mode") == "fail_n_times" and "fail_times" not in c:
                raise ValueError("fail_n_times needs fail_times")

    def _matches_args(self, cfg: dict, args: dict) -> bool:
        ma = cfg.get("match_args") or {}
        return all(str(args.get(k)) == str(v) for k, v in ma.items())

    def _fault_error(self, cfg: dict) -> tuple[bool, dict]:
        err = dict(cfg.get("error") or {"code": "INJECTED_FAULT", "message": "injected fault"})
        err.setdefault("code", "INJECTED_FAULT")
        err.setdefault("message", "injected fault")
        return False, {"error": {**err, "injected": True}}

    def dispatch(self, world: WorldState, name: str, args: dict) -> tuple[bool, Any]:
        for cfg in self.cfgs:
            if cfg.get("tool") != name:
                continue
            mode = cfg["mode"]
            if mode == "always":
                return self._fault_error(cfg)
            if mode == "fail_n_times":
                n = self._counts.get(name, 0)
                if n < int(cfg["fail_times"]):
                    self._counts[name] = n + 1
                    return self._fault_error(cfg)
            if mode == "invalid_on" and self._matches_args(cfg, args or {}):
                return self._fault_error(cfg)
        return real_dispatch(world, name, args)
