# -*- coding: utf-8 -*-
"""Run the evaluation matrix.

Examples:
  python scripts/run_eval.py --mock oracle                 # offline E2E
  python scripts/run_eval.py --mock chaos
  python scripts/run_eval.py --models deepseek-chat,deepseek-reasoner
  python scripts/run_eval.py --stability --models deepseek-chat

Resume: existing trajectories are skipped unless --force.
Budget: CostTracker hard caps (TCB_CAP_B1 / TCB_CAP_GLOBAL); on breach the
run stops cleanly, partial results stay on disk, blocker note is written.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tcb import config  # noqa: E402
from tcb.cost import BudgetExceeded, CostTracker  # noqa: E402
from tcb.grading.grade import grade_task  # noqa: E402
from tcb.harness.llm import DeepSeekProvider, OutOfBalance  # noqa: E402
from tcb.harness.mock import ChaoticMock, OracleMock  # noqa: E402
from tcb.harness.runner import run_task  # noqa: E402
from tcb.tasks.loader import load_tasks  # noqa: E402

TRAJ_DIR = config.RESULTS_DIR / "trajectories"
GRADES_PATH = config.RESULTS_DIR / "grades.jsonl"


def stability_subset(tasks: list[dict], k: int) -> list[dict]:
    by_domain: dict[str, list[dict]] = {}
    for t in sorted(tasks, key=lambda x: x["id"]):
        by_domain.setdefault(t["domain"], []).append(t)
    out: list[dict] = []
    while len(out) < k and by_domain:
        for d in sorted(by_domain):
            if by_domain[d] and len(out) < k:
                out.append(by_domain[d].pop(0))
    return out


def make_provider(spec: str, task: dict, tracker: CostTracker):
    if spec == "oracle":
        p = OracleMock(task)
        return p
    if spec == "chaos":
        return ChaoticMock(task, seed=hash(task["id"]) % 1000)
    return DeepSeekProvider(spec, tracker)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=",".join(config.MODELS))
    ap.add_argument("--mock", choices=["oracle", "chaos"], default=None)
    ap.add_argument("--tasks", default="all", help="all | comma-separated ids")
    ap.add_argument("--stability", action="store_true",
                    help="run the stability subset with STABILITY_REPEATS repeats")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    tasks = load_tasks()
    if args.tasks != "all":
        want = set(args.tasks.split(","))
        tasks = [t for t in tasks if t["id"] in want]
    if args.stability:
        tasks = stability_subset(tasks, config.STABILITY_SUBSET_SIZE)
        args.repeat = max(args.repeat, config.STABILITY_REPEATS)

    model_specs = [args.mock] if args.mock else args.models.split(",")
    tracker = CostTracker(phase="B1")
    GRADES_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    units = [(m, t, r) for m in model_specs for t in tasks
             for r in range(args.repeat)]
    print(f"[eval] {len(units)} units "
          f"({len(model_specs)} models x {len(tasks)} tasks x {args.repeat} runs)")
    stopped = False
    t0 = time.time()
    n_done = n_pass = n_skip = 0

    with GRADES_PATH.open("a", encoding="utf-8") as gf:
        for model, task, run_idx in units:
            out_fp = TRAJ_DIR / model / f"{task['id']}__r{run_idx}.json"
            if out_fp.exists() and not args.force:
                n_skip += 1
                traj = json.loads(out_fp.read_text(encoding="utf-8"))
            else:
                if stopped:
                    continue
                try:
                    provider = make_provider(model, task, tracker)
                    traj = run_task(provider, task, run_idx=run_idx,
                                    out_dir=TRAJ_DIR)
                except (BudgetExceeded, OutOfBalance) as e:
                    print(f"[eval] BUDGET STOP: {e}")
                    stopped = True
                    continue
                except Exception as e:  # noqa: BLE001
                    print(f"[eval] unit error {model}/{task['id']}: "
                          f"{type(e).__name__}: {str(e)[:200]}")
                    continue
            g = grade_task(task, traj)
            gf.write(json.dumps(g, ensure_ascii=False) + "\n")
            gf.flush()
            n_done += 1
            n_pass += int(g["task_pass"])
            flag = "PASS" if g["task_pass"] else "FAIL"
            print(f"[eval] {flag} {model:>18} {task['id']} r{run_idx} "
                  f"sel={g['tool_selection_rate']:.2f} par={g['param_accuracy']:.2f} "
                  f"hall={g['n_hallucinated_args']} final={int(g['final_answer_ok'])} "
                  f"({g['n_calls']} calls, {g['wall_seconds']}s)")

    print(f"[eval] done={n_done} pass={n_pass} skipped(existing)={n_skip} "
          f"stopped={stopped} spend={tracker.phase_total:.2f}CNY "
          f"wall={time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
