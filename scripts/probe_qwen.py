# -*- coding: utf-8 -*-
"""Probe Qwen models via Aliyun Bailian (DashScope compatible-mode):
function-calling support + key validity. Usage: python scripts/probe_qwen.py
Key never printed. Models with no tool support are reported, not fatal.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openai import OpenAI

from tcb import config

TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get current weather for a city",
        "parameters": {"type": "object",
                       "properties": {"city": {"type": "string"}},
                       "required": ["city"]},
    },
}

MODELS = ["qwen-max", "qwen-plus", "qwen-turbo", "qwen-flash",
          # Bailian Token-Plan models (sk-sp- key)
          "qwen3.5-plus", "qwen3.5-flash", "kimi-k3", "glm-5",
          "MiniMax-M3", "deepseek-v3.2"]


def probe(model: str) -> dict:
    out = {"model": model}
    try:
        key = config.load_key(model)
        if not key:
            out["ok"] = False
            out["error"] = "no DASHSCOPE_API_KEY"
            return out
        client = OpenAI(api_key=key, base_url=config.base_url_for(model),
                        timeout=60, max_retries=1)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user",
                       "content": "What is the weather in Wuhan? Use the tool."}],
            tools=[TOOL], temperature=0, max_tokens=200)
        msg = resp.choices[0].message
        out["ok"] = True
        out["tool_calls"] = bool(msg.tool_calls)
        if msg.tool_calls:
            out["call"] = msg.tool_calls[0].function.name
            out["args"] = msg.tool_calls[0].function.arguments[:60]
        u = resp.usage
        out["usage"] = {"prompt": u.prompt_tokens, "completion": u.completion_tokens}
    except Exception as e:  # noqa: BLE001
        out["ok"] = False
        out["error"] = f"{type(e).__name__}: {str(e)[:220]}"
    return out


if __name__ == "__main__":
    results = [probe(m) for m in MODELS]
    print(json.dumps(results, ensure_ascii=False, indent=1))
    ok = [r["model"] for r in results if r["ok"] and r.get("tool_calls")]
    no_tool = [r["model"] for r in results if r["ok"] and not r.get("tool_calls")]
    bad = [(r["model"], r.get("error", "")[:80]) for r in results if not r["ok"]]
    print("TOOL-OK:", ok)
    print("NO-TOOL-SUPPORT:", no_tool)
    print("FAILED:", bad)
    sys.exit(0 if ok else 1)
