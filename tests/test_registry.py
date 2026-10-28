# -*- coding: utf-8 -*-
"""Model registry invariants: keys double as trajectory directory names, so
they must be filesystem-safe on Windows; wire ids live in api_model."""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tcb import config

_ILLEGAL = re.compile(r'[<>:"/\\|?*]')


def test_registry_keys_are_filesystem_safe():
    bad = [m for m in config.MODEL_REGISTRY if _ILLEGAL.search(m)]
    assert not bad, f"registry keys used as dir names must avoid <>:\"/\\|?* : {bad}"


def test_every_real_model_has_endpoint_and_key_route():
    for name, reg in config.MODEL_REGISTRY.items():
        if name == "mock":
            continue
        assert reg["base_url"], name
        assert reg.get("key_literal") or reg.get("key_env"), \
            f"{name} has neither key_env nor key_literal"
        assert "pricing" in reg and {"input", "output"} <= set(reg["pricing"]), name


def test_pricing_table_covers_registry():
    assert set(config.PRICING) == set(config.MODEL_REGISTRY)


def test_ollama_local_entries_resolve_without_env(monkeypatch):
    """Local endpoints need no secret; a missing env var must not block them."""
    for name in ("DASHSCOPE_API_KEY", "BAILIAN_API_KEY", "DEEPSEEK_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    key = config.load_key("ollama-qwen2.5-7b-instruct")
    assert key, "local ollama entry must resolve a literal key"
    assert config.base_url_for("ollama-qwen2.5-7b-instruct").startswith("http://localhost")


def test_api_model_differs_from_key_for_ollama():
    reg = config.MODEL_REGISTRY["ollama-qwen2.5-7b-instruct"]
    assert reg["api_model"] == "qwen2.5:7b-instruct"
    assert ":" not in "ollama-qwen2.5-7b-instruct"


def test_unknown_model_raises():
    with pytest.raises(KeyError):
        config.load_key("no-such-model")
