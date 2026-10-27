# -*- coding: utf-8 -*-
"""API probe: verify DeepSeek key works and check function-calling support.

Usage: python scripts/probe_api.py
Reads key via TCB_ENV_FILE (default: <repo>/.env). The key is never printed.
"""
import json
import sys
from pathlib import Path

from dotenv import dotenv_values
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tcb import config  # noqa: E402

ENV_PATH = config.DEEPSEEK_ENV
BASE_URL = config.BASE_URL

WEATHER_TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get current weather for a city",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"},
            },
            "required": ["city"],
        },
    },
}


def probe(model: str, client: OpenAI) -> dict:
    out = {"model": model}
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "What is the weather in Wuhan right now? Use the tool."}],
            tools=[WEATHER_TOOL],
            temperature=0,
            max_tokens=300,
        )
        msg = resp.choices[0].message
        out["ok"] = True
        out["tool_calls"] = bool(msg.tool_calls)
        if msg.tool_calls:
            out["first_call"] = {
                "name": msg.tool_calls[0].function.name,
                "arguments": msg.tool_calls[0].function.arguments,
            }
        out["content_head"] = (msg.content or "")[:120]
        u = resp.usage
        out["usage"] = {
            "prompt_tokens": u.prompt_tokens,
            "completion_tokens": u.completion_tokens,
            "total_tokens": u.total_tokens,
        }
    except Exception as e:  # noqa: BLE001
        out["ok"] = False
        out["error"] = f"{type(e).__name__}: {str(e)[:300]}"
    return out


def main() -> int:
    cfg = dotenv_values(ENV_PATH)
    key = cfg.get("DEEPSEEK_API_KEY")
    if not key:
        print(json.dumps({"fatal": "no DEEPSEEK_API_KEY in deploy/.env"}))
        return 2
    client = OpenAI(api_key=key, base_url=BASE_URL, timeout=60, max_retries=1)
    results = [probe(m, client) for m in ("deepseek-chat", "deepseek-reasoner")]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
