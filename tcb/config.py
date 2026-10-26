# -*- coding: utf-8 -*-
"""Central configuration: paths, pricing, budget caps, model list."""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
RESULTS_DIR = REPO_ROOT / "results"
TASKS_DIR = REPO_ROOT / "tasks"

WORLD_PATH = DATA_DIR / "world.json"
COST_LEDGER = RESULTS_DIR / "cost_ledger.jsonl"
BLOCKER_REPORT = REPO_ROOT / "BLOCKER_REPORT.md"

DEEPSEEK_ENV = Path(
    os.environ.get(
        "TCB_ENV_FILE",
        r"G:\C盘大文件迁移\claude code projects\smartagri-rx\deploy\.env",
    )
)
BASE_URL = "https://api.deepseek.com"

# CNY per 1M tokens (DeepSeek list price, configurable)
PRICING = {
    "deepseek-chat": {"input": 2.0, "output": 8.0},
    "deepseek-reasoner": {"input": 4.0, "output": 16.0},
    "mock": {"input": 0.0, "output": 0.0},
}

MODELS = ["deepseek-chat", "deepseek-reasoner"]

# Budget fuses (CNY). On breach: switch to mock/skip + write BLOCKER_REPORT.md.
BUDGET_CAP_B1 = float(os.environ.get("TCB_CAP_B1", "28"))
BUDGET_CAP_GLOBAL = float(os.environ.get("TCB_CAP_GLOBAL", "40"))

WORLD_SEED = 20261026
TODAY = "2026-10-27"  # fixed "today" inside the sandbox world (deterministic)

STABILITY_SUBSET_SIZE = 15
STABILITY_REPEATS = 3
DEFAULT_MAX_TURNS = 8
DEFAULT_TEMPERATURE = 0.0
