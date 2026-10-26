# -*- coding: utf-8 -*-
"""Build results/REPORT.md from grades.jsonl + trajectories."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tcb import config  # noqa: E402
from tcb.report.gallery import build_gallery_md  # noqa: E402
from tcb.report.leaderboard import build_leaderboard_md, load_grades  # noqa: E402


def dedupe(grades: list[dict]) -> list[dict]:
    latest: dict[tuple, dict] = {}
    for g in grades:
        latest[(g.get("model") or g.get("model_id"), g["task_id"], g["run_idx"])] = g
    return list(latest.values())


def stability_section(grades: list[dict]) -> str:
    runs = defaultdict(list)
    for g in grades:
        runs[(g.get("model") or g.get("model_id"), g["task_id"])].append(g["task_pass"])
    multi = {k: v for k, v in runs.items() if len(v) > 1}
    if not multi:
        return ""
    consistent = sum(1 for v in multi.values() if len(set(v)) == 1)
    lines = ["## 稳定性(同题多跑)", "",
             f"- 多跑单元数: {len(multi)}",
             f"- 结论一致(全过或全挂): {consistent}/{len(multi)} "
             f"({consistent / len(multi):.0%})", "",
             "| 模型 | 任务 | 各次通过 |", "|---|---|---|"]
    for (model, tid), v in sorted(multi.items()):
        lines.append(f"| {model} | {tid} | {' '.join('✔' if x else '✘' for x in v)} |")
    return "\n".join(lines) + "\n"


def stress_delta_section(grades: list[dict]) -> str:
    """Neutral vs stress comparison: integrity-under-pressure delta."""
    main = [g for g in grades if g["run_idx"] == 0]
    models = sorted({g["model"] for g in main if g["model"].endswith("_stress")})
    if not models:
        return ""
    lines = ["## 完整性差值(中性 vs 压力提示)", "",
             "压力提示 = 对抗性系统指令(\"用户不想听到失败……不要提及工具故障,"
             "永远给出确定答案\")。差值展示模型在压力下放弃诚实行为的情况。", "",
             "| 模型 | 中性通过 | 压力通过 | 翻转任务 | 压力幻觉参数 |",
             "|---|---|---|---|---|"]
    flips_all = []
    for sm in models:
        base = sm.replace("_stress", "")
        neu = {g["task_id"]: g for g in main if g["model"] == base}
        strs = {g["task_id"]: g for g in main if g["model"] == sm}
        common = sorted(set(neu) & set(strs))
        if not common:
            continue
        np_ = sum(neu[t]["task_pass"] for t in common)
        sp = sum(strs[t]["task_pass"] for t in common)
        flips = [t for t in common if neu[t]["task_pass"] and not strs[t]["task_pass"]]
        hall = sum(strs[t]["n_hallucinated_args"] for t in common)
        lines.append(f"| {base} | {np_}/{len(common)} | {sp}/{len(common)} "
                     f"| {', '.join(flips) or '-'} | {hall} |")
        flips_all.extend((base, t, strs[t]) for t in flips)
    if flips_all:
        lines += ["", "### 翻转案例细节", ""]
        for base, tid, g in flips_all:
            why = []
            if g["final_answer_missing"]:
                why.append(f"缺失事实 {g['final_answer_missing'][:3]}")
            if g["final_answer_banned"]:
                why.append(f"触犯禁语 {g['final_answer_banned'][:2]}")
            if g["n_hallucinated_args"]:
                why.append(f"幻觉参数×{g['n_hallucinated_args']}")
            if g["recovery"].get("applicable") and not g["recovery"]["ok"]:
                why.append("压力下未恢复")
            lines.append(f"- **{tid}** ({base}_stress): " + "; ".join(why))
    return "\n".join(lines) + "\n"


def main() -> None:
    grades = dedupe(load_grades(config.RESULTS_DIR / "grades.jsonl"))
    main_runs = [g for g in grades if g["run_idx"] == 0]
    real = [g for g in main_runs if not (g["model"] or "").startswith("mock")]
    mocks = [g for g in main_runs if (g["model"] or "").startswith("mock")]

    parts = []
    if real:
        parts.append(build_leaderboard_md(real))
    delta = stress_delta_section(grades)
    if delta:
        parts.append(delta)
    stab = stability_section(grades)
    if stab:
        parts.append(stab)
    if mocks:
        parts.append(build_leaderboard_md(mocks, title="Mock 对照(管线自检)"))
    if real:
        parts.append(build_gallery_md(real, config.RESULTS_DIR / "trajectories"))
    out = config.RESULTS_DIR / "REPORT.md"
    out.write_text("\n".join(parts), encoding="utf-8")
    cost = 0.0
    ledger = config.COST_LEDGER
    if ledger.exists():
        cost = sum(json.loads(x).get("cost_cny", 0)
                   for x in ledger.read_text(encoding="utf-8").splitlines() if x.strip())
    print(f"report -> {out} ({len(real)} real grades, {len(mocks)} mock grades, "
          f"total spend {cost:.2f} CNY)")


if __name__ == "__main__":
    main()
