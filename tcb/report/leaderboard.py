# -*- coding: utf-8 -*-
"""Aggregate grade records into a markdown leaderboard."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


def load_grades(path: Path) -> list[dict]:
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _agg(records: list[dict]) -> dict:
    n = len(records)
    if not n:
        return {}
    passes = sum(r["task_pass"] for r in records)
    sel = sum(r["tool_selection_rate"] for r in records) / n
    par = sum(r["param_accuracy"] for r in records) / n
    fa = sum(r["final_answer_ok"] for r in records) / n
    hall = sum(r["n_hallucinated_args"] for r in records)
    hall100 = sum(r["hallucination_per_100_args"] for r in records) / n
    sv = sum(r["schema_violations"] for r in records)
    recs = [r for r in records if r["recovery"].get("applicable")]
    rec = (sum(r["recovery"]["ok"] for r in recs) / len(recs)) if recs else float("nan")
    turns = sum(r["n_calls"] or 0 for r in records) / n
    wall = sum(r["wall_seconds"] or 0 for r in records) / n
    return {"n": n, "pass_rate": passes / n, "tool_selection": sel,
            "param_accuracy": par, "final_answer": fa,
            "hallucinated_args": hall, "hall_per_100": hall100,
            "schema_violations": sv, "recovery_rate": rec,
            "avg_calls": turns, "avg_wall_s": wall}


def build_leaderboard_md(grades: list[dict], title: str = "ToolCallBench-CN 排行榜") -> str:
    by_model: dict[str, list[dict]] = defaultdict(list)
    for r in grades:
        by_model[r.get("model") or r.get("model_id") or "?"].append(r)
    lines = [f"# {title}", "",
             "指标定义: 通过率=全部主指标联合; 工具选对=required 工具成功调用比例; "
             "参数精确=required 调用声明匹配器通过比例; 幻觉=无溯源参数值(每百参数); "
             "自愈=故障题恢复率; 终答=must_include/ must_not_include 核验。", "",
             "| 模型 | 任务数 | 通过率 | 工具选对 | 参数精确 | 幻觉/100参数 | 自愈率 | 终答正确 | 平均调用数 |",
             "|---|---|---|---|---|---|---|---|---|"]
    for model, recs in sorted(by_model.items()):
        a = _agg(recs)
        if not a:
            continue
        lines.append(
            f"| {model} | {a['n']} | {a['pass_rate']:.1%} | {a['tool_selection']:.1%} "
            f"| {a['param_accuracy']:.1%} | {a['hall_per_100']:.2f} "
            f"| {a['recovery_rate']:.1%} | {a['final_answer']:.1%} | {a['avg_calls']:.1f} |")

    # per-domain breakdown
    lines += ["", "## 分域通过率", "", "| 模型 | " +
              " | ".join(sorted({r['domain'] for r in grades})) + " |",
              "|---" * (len({r['domain'] for r in grades}) + 1) + "|"]
    domains = sorted({r["domain"] for r in grades})
    for model, recs in sorted(by_model.items()):
        row = [model]
        for d in domains:
            sub = [r for r in recs if r["domain"] == d]
            row.append(f"{sum(r['task_pass'] for r in sub)}/{len(sub)}" if sub else "-")
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines) + "\n"
