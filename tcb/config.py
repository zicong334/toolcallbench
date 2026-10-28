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
    os.environ.get("TCB_ENV_FILE") or (REPO_ROOT / ".env")
)
BASE_URL = "https://api.deepseek.com"

# Model registry: model_id -> provider endpoint, key env var, pricing.
# Pricing = CNY per 1M tokens, ESTIMATES for the budget fuse only
# (verify against vendor price lists; ledger records real token counts).
MODEL_REGISTRY = {
    "deepseek-chat": {
        "base_url": "https://api.deepseek.com",
        "key_env": ("DEEPSEEK_API_KEY",),
        "pricing": {"input": 2.0, "output": 8.0},
    },
    "deepseek-reasoner": {
        "base_url": "https://api.deepseek.com",
        "key_env": ("DEEPSEEK_API_KEY",),
        "pricing": {"input": 4.0, "output": 16.0},
    },
    # Aliyun Bailian / DashScope (OpenAI-compatible mode)
    "qwen-max": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "key_env": ("DASHSCOPE_API_KEY", "BAILIAN_API_KEY"),
        "pricing": {"input": 2.4, "output": 9.6},
    },
    "qwen-plus": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "key_env": ("DASHSCOPE_API_KEY", "BAILIAN_API_KEY"),
        "pricing": {"input": 0.8, "output": 2.0},
    },
    "qwen-turbo": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "key_env": ("DASHSCOPE_API_KEY", "BAILIAN_API_KEY"),
        "pricing": {"input": 0.3, "output": 0.6},
    },
    "qwen-flash": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "key_env": ("DASHSCOPE_API_KEY", "BAILIAN_API_KEY"),
        "pricing": {"input": 0.0, "output": 0.0},
    },
    # --- Bailian "Token Plan" (套餐专属 sk-sp- key) models.
    # The plan bills per CALL from a quota, not per token; pricing below are
    # shadow estimates (list-price analogues) so the budget fuse still works.
    # Endpoint pending verification with a valid plan key (probe_qwen.py).
    "qwen3.5-plus": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "key_env": ("DASHSCOPE_API_KEY", "BAILIAN_API_KEY"),
        "pricing": {"input": 0.8, "output": 2.0},
    },
    "qwen3.5-flash": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "key_env": ("DASHSCOPE_API_KEY", "BAILIAN_API_KEY"),
        "pricing": {"input": 0.0, "output": 0.0},
    },
    "kimi-k3": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "key_env": ("DASHSCOPE_API_KEY", "BAILIAN_API_KEY"),
        "pricing": {"input": 4.0, "output": 16.0},
    },
    "kimi-k2.6": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "key_env": ("DASHSCOPE_API_KEY", "BAILIAN_API_KEY"),
        "pricing": {"input": 4.0, "output": 16.0},
    },
    "glm-5": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "key_env": ("DASHSCOPE_API_KEY", "BAILIAN_API_KEY"),
        "pricing": {"input": 2.0, "output": 8.0},
    },
    "MiniMax-M3": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "key_env": ("DASHSCOPE_API_KEY", "BAILIAN_API_KEY"),
        "pricing": {"input": 2.0, "output": 8.0},
    },
    "deepseek-v3.2": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "key_env": ("DASHSCOPE_API_KEY", "BAILIAN_API_KEY"),
        "pricing": {"input": 2.0, "output": 8.0},
    },
    "mock": {"base_url": "", "key_env": (), "pricing": {"input": 0.0, "output": 0.0}},
    # --- Local Ollama (zero cost, no account, CPU inference).
    # Lets anyone reproduce a leaderboard tier without any API key.
    "ollama-qwen2.5-7b-instruct": {
        "base_url": "http://localhost:11434/v1",
        "api_model": "qwen2.5:7b-instruct",
        "key_env": (), "key_literal": "ollama",
        "pricing": {"input": 0.0, "output": 0.0},
    },
    "ollama-llama3.1-8b-instruct": {
        "base_url": "http://localhost:11434/v1",
        "api_model": "llama3.1:8b-instruct",
        "key_env": (), "key_literal": "ollama",
        "pricing": {"input": 0.0, "output": 0.0},
    },
    "ollama-qwen2.5-14b-instruct": {
        "base_url": "http://localhost:11434/v1",
        "api_model": "qwen2.5:14b-instruct",
        "key_env": (), "key_literal": "ollama",
        "pricing": {"input": 0.0, "output": 0.0},
    },
}

# Back-compat: PRICING derived from registry
PRICING = {m: r["pricing"] for m, r in MODEL_REGISTRY.items()}

MODELS = ["deepseek-chat", "deepseek-reasoner"]


def load_key(model: str) -> str | None:
    """Resolve API key for a registry model.

    Order: literal key in the registry (local endpoints that ignore auth),
    then each name in key_env looked up in os.environ and the repo .env.
    """
    from dotenv import dotenv_values
    reg = MODEL_REGISTRY.get(model)
    if not reg:
        raise KeyError(f"model {model!r} not in MODEL_REGISTRY")
    if reg.get("key_literal"):
        return reg["key_literal"]
    file_cfg = dotenv_values(DEEPSEEK_ENV) if DEEPSEEK_ENV.exists() else {}
    for name in reg["key_env"]:
        val = os.environ.get(name) or file_cfg.get(name)
        if val:
            return val
    return None


def base_url_for(model: str) -> str:
    return MODEL_REGISTRY[model]["base_url"]

# Budget fuses (CNY). On breach: switch to mock/skip + write BLOCKER_REPORT.md.
BUDGET_CAP_B1 = float(os.environ.get("TCB_CAP_B1", "28"))
BUDGET_CAP_GLOBAL = float(os.environ.get("TCB_CAP_GLOBAL", "40"))

WORLD_SEED = 20261026
TODAY = "2026-10-27"  # fixed "today" inside the sandbox world (deterministic)

STABILITY_SUBSET_SIZE = 15
STABILITY_REPEATS = 3
DEFAULT_MAX_TURNS = 8
DEFAULT_TEMPERATURE = 0.0
