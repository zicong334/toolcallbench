# -*- coding: utf-8 -*-
"""DeepSeek provider: OpenAI-compatible chat with tools, retry/backoff,
budget hooks, and hard 402 handling (never burn silently)."""
from __future__ import annotations

import time
from typing import Any

from openai import OpenAI

from .. import config
from ..cost import BudgetExceeded, CostTracker, write_blocker

RETRYABLE_STATUS = {429, 500, 502, 503, 504}

# back-compat alias
DeepSeekProvider = None  # set after class definition below


class OutOfBalance(RuntimeError):
    pass


class OpenAICompatProvider:
    """Any OpenAI-compatible endpoint in the model registry (DeepSeek,
    Aliyun Bailian/DashScope Qwen, ...). Key resolution: os.environ or the
    repo .env, via config.load_key()."""
    name = "openai-compat"

    def __init__(self, model: str, tracker: CostTracker,
                 temperature: float = config.DEFAULT_TEMPERATURE,
                 max_tokens: int = 1500, max_retries: int = 4):
        self.model = model
        self.name = model  # trajectory folders are keyed by provider name
        self.tracker = tracker
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        key = config.load_key(model)
        if not key:
            reg = config.MODEL_REGISTRY[model]
            raise RuntimeError(
                f"no API key for {model}: set one of {reg['key_env']} in env "
                f"or in {config.DEEPSEEK_ENV}")
        self.client = OpenAI(api_key=key, base_url=config.base_url_for(model),
                             timeout=120, max_retries=0)

    def complete(self, messages: list[dict], tools: list[dict],
                 task_id: str = "") -> dict[str, Any]:
        """One chat completion. Returns normalized assistant message dict:
        {"role": "assistant", "content": str|None,
         "tool_calls": [{"id", "name", "arguments": dict, "raw_arguments": str}]}
        Raises BudgetExceeded / OutOfBalance (caller degrades gracefully)."""
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools or None,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
                msg = resp.choices[0].message
                u = resp.usage
                try:
                    self.tracker.charge(self.model, u.prompt_tokens,
                                        u.completion_tokens, task_id=task_id)
                except BudgetExceeded as be:
                    write_blocker(
                        "预算硬顶触发",
                        f"cost ledger 到顶: {be}",
                        "未试: 继续真实评测(会超预算)",
                        "已切换 mock/暂停真实跑分, 余额与硬顶由负责人裁决后调整 TCB_CAP_B1 重跑",
                    )
                    raise
                calls = []
                for tc in msg.tool_calls or []:
                    raw = tc.function.arguments
                    try:
                        import json
                        args = json.loads(raw) if raw else {}
                        if not isinstance(args, dict):
                            args = {"_non_object": args}
                    except Exception:  # noqa: BLE001
                        args = {"_unparseable": raw}
                    calls.append({"id": tc.id, "name": tc.function.name,
                                  "arguments": args, "raw_arguments": raw})
                return {"role": "assistant", "content": msg.content,
                        "tool_calls": calls,
                        "usage": {"prompt_tokens": u.prompt_tokens,
                                  "completion_tokens": u.completion_tokens}}
            except BudgetExceeded:
                raise
            except Exception as e:  # noqa: BLE001
                s = str(e)
                status = getattr(e, "status_code", None)
                if status in (402, 401) or any(w in s.lower() for w in (
                        "balance", "insufficient", "arrears", "arrearage",
                        "invalidapikey", "invalid api key", "allocationquota",
                        "quota exceeded", "exceeded your current quota")):
                    write_blocker(
                        "DeepSeek 402/余额不足",
                        f"attempt {attempt + 1}: {type(e).__name__}: {s[:200]}",
                        "未试: 充值后重跑(命令见 HANDOVER)",
                        "真实评测中止, 请充值后用 run_eval.py 断点续跑",
                    )
                    raise OutOfBalance(s[:200]) from e
                if status in RETRYABLE_STATUS or "timeout" in s.lower() or "connection" in s.lower():
                    last_exc = e
                    wait = min(2 ** attempt * 2, 30)
                    time.sleep(wait)
                    continue
                last_exc = e
                break
        raise RuntimeError(f"provider failed after retries: {last_exc}")


# back-compat alias (run_eval and tests import this name)
DeepSeekProvider = OpenAICompatProvider
