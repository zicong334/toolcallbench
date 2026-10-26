# -*- coding: utf-8 -*-
"""Cost tracking with hard budget fuses.

Every LLM call reports usage here. The ledger is append-only JSONL so spend
survives crashes. When a cap is breached, BudgetExceeded is raised and the
caller must degrade gracefully (mock mode) and record a blocker note.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from . import config


class BudgetExceeded(RuntimeError):
    pass


class CostTracker:
    def __init__(self, ledger_path: Path | None = None, phase: str = "B1"):
        self.ledger_path = Path(ledger_path or config.COST_LEDGER)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self.phase = phase  # "B1" or "B2"
        self._lock = threading.Lock()
        self.total = self._load_existing_total()
        self.phase_total = 0.0

    def _load_existing_total(self) -> float:
        total = 0.0
        if self.ledger_path.exists():
            for line in self.ledger_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    total += float(json.loads(line).get("cost_cny", 0.0))
                except (json.JSONDecodeError, ValueError):
                    continue
        return total

    @staticmethod
    def cost_of(model: str, prompt_tokens: int, completion_tokens: int) -> float:
        p = config.PRICING.get(model)
        if not p:
            raise KeyError(f"no pricing for model {model!r}")
        return prompt_tokens / 1e6 * p["input"] + completion_tokens / 1e6 * p["output"]

    def charge(self, model: str, prompt_tokens: int, completion_tokens: int,
               task_id: str = "", note: str = "") -> float:
        cost = self.cost_of(model, prompt_tokens, completion_tokens)
        rec = {
            "ts": round(time.time(), 2),
            "phase": self.phase,
            "model": model,
            "task_id": task_id,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost_cny": round(cost, 6),
            "note": note,
        }
        with self._lock:
            with self.ledger_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            self.total += cost
            self.phase_total += cost
            cap = config.BUDGET_CAP_B1 if self.phase == "B1" else config.BUDGET_CAP_GLOBAL
            if self.phase_total > cap or self.total > config.BUDGET_CAP_GLOBAL:
                raise BudgetExceeded(
                    f"phase={self.phase} phase_total={self.phase_total:.2f} "
                    f"total={self.total:.2f} cap={cap:.2f}"
                )
        return cost


def write_blocker(title: str, tried: str, not_tried: str, recommendation: str) -> None:
    """Append a blocker note (report-before-plan-change discipline)."""
    config.BLOCKER_REPORT.parent.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    entry = (
        f"\n## [{stamp}] {title}\n"
        f"- 已试: {tried}\n- 未试: {not_tried}\n- 推荐: {recommendation}\n"
    )
    with config.BLOCKER_REPORT.open("a", encoding="utf-8") as f:
        if f.tell() == 0:
            f.write("# BLOCKER REPORT(通宵流水线,待负责人裁决)\n")
        f.write(entry)
