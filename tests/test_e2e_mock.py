# -*- coding: utf-8 -*-
"""Offline E2E: OracleMock must pass every task; ChaoticMock must fail.

Only top-level tasks/*.yaml (gold examples) are loaded here so the test is
stable while batch files are still being authored.
"""
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tcb.grading.grade import grade_task
from tcb.harness.mock import ChaoticMock, OracleMock
from tcb.harness.runner import run_task
from tcb.tasks.loader import validate_task

ROOT = Path(__file__).resolve().parent.parent


def _load_samples():
    out = []
    for fp in sorted((ROOT / "tasks").glob("*.yaml")):
        t = yaml.safe_load(fp.read_text(encoding="utf-8"))
        validate_task(t, fp.name)
        out.append(t)
    return out


def test_samples_valid():
    samples = _load_samples()
    assert len(samples) >= 7


def test_oracle_passes_everything():
    failures = []
    for task in _load_samples():
        traj = run_task(OracleMock(task), task)
        g = grade_task(task, traj)
        if not g["task_pass"]:
            failures.append((task["id"], g["status"], g["required_detail"],
                             g["final_answer_missing"], g["final_answer_banned"],
                             g["hallucinations"][:3], g["recovery"]))
    assert not failures, failures


def test_chaos_gets_caught():
    caught = 0
    total = 0
    for task in _load_samples():
        traj = run_task(ChaoticMock(task), task)
        g = grade_task(task, traj)
        total += 1
        if not g["task_pass"]:
            caught += 1
    # chaos fabricates success and calls wrong tools; must fail on nearly all
    assert caught >= total * 0.8, f"only {caught}/{total} caught"
