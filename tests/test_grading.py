# -*- coding: utf-8 -*-
"""Matcher, hallucination-detection and grading unit tests."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tcb.grading.grade import grade_task
from tcb.grading.hallucination import ProvenanceIndex, scan_trajectory
from tcb.grading.matchers import match

TASK = {
    "id": "X-001", "domain": "weather", "lang": "zh",
    "instruction": "查询武汉2026-10-28的天气,报告最高气温和湿度。",
    "tools": ["get_weather", "list_events"],
    "max_turns": 6,
    "grading": {
        "required_calls": [
            {"tool": "get_weather",
             "args": {"city": {"equals": "武汉"}, "date": {"equals": "2026-10-28"}}},
        ],
        "final_answer": {"must_include": ["9", "57"],
                         "must_not_include": ["不知道"]},
    },
}


def _call(seq, tool, args, ok=True, injected=False, code=None, result=None):
    return {"seq": seq, "tool": tool, "args": args, "ok": ok,
            "injected": injected, "error_code": code,
            "result": result if result is not None else {"ok": 1}}


def _traj(calls, final, status="completed"):
    return {"task_id": TASK["id"], "status": status, "calls": calls,
            "final_content": final, "n_turns": 2, "wall_seconds": 1,
            "model": "test", "model_id": "test", "run_idx": 0,
            "usage": {"prompt_tokens": 0, "completion_tokens": 0}}


def test_matchers():
    assert match({"equals": "武汉"}, "武汉")
    assert match({"equals": 1}, "1")
    assert match({"equals": 599.0}, "599")
    assert match({"in_set": ["FL0007", "FL0009"]}, "FL0009")
    assert match({"numeric": {"value": 241.65, "tol": 0.01}}, "241.654")
    assert match({"contains": "耳机"}, "降噪耳机pro")
    assert match({"regex": r"^\d{2}:\d{2}$"}, "10:30")
    assert match({"any": None}, object())
    assert not match({"equals": "北京"}, "武汉")
    assert not match({"equals": "x"}, None)


def test_grade_pass():
    t = _traj([_call(0, "get_weather", {"city": "武汉", "date": "2026-10-28"},
                     result={"temp_high_c": 9})],
              "武汉10月28日最高气温9°C,湿度57%。")
    g = grade_task(TASK, t)
    assert g["task_pass"] and g["tool_selection_rate"] == 1.0
    assert g["param_accuracy"] == 1.0 and g["final_answer_ok"]


def test_grade_wrong_params():
    t = _traj([_call(0, "get_weather", {"city": "武汉", "date": "2026-10-29"},
                     result={"temp_high_c": 11})],
              "最高气温9°C,湿度57%。")
    g = grade_task(TASK, t)
    assert not g["task_pass"] and g["param_accuracy"] == 0.5


def test_grade_missing_final():
    t = _traj([_call(0, "get_weather", {"city": "武汉", "date": "2026-10-28"})],
              "抱歉,我不知道。")
    g = grade_task(TASK, t)
    assert not g["final_answer_ok"] and g["final_answer_banned"] == ["不知道"]


def test_grade_failed_call_does_not_satisfy():
    t = _traj([_call(0, "get_weather", {"city": "武汉", "date": "2026-10-28"},
                     ok=False, code="RATE_LIMITED")],
              "最高气温9°C,湿度57%。")
    g = grade_task(TASK, t)
    assert not g["task_pass"]  # required call never succeeded


def test_hallucination_detection():
    calls = [
        _call(0, "get_weather", {"city": "武汉", "date": "2026-10-28"}),
        _call(1, "list_events", {"date": "2026-12-25"}),  # date outside world
    ]
    h = scan_trajectory(TASK, calls)
    assert any(x["arg"] == "date" and x["value"] == "2026-12-25" for x in h)
    idx = ProvenanceIndex(TASK)
    assert idx.is_grounded("武汉")          # in instruction
    assert idx.is_grounded(3)               # small int
    assert not idx.is_grounded("FL9999")    # invented id


def test_hallucination_grounded_by_prior_results():
    calls = [
        _call(0, "get_weather", {"city": "武汉"},
              result={"city": "武汉", "special_id": "WX-77"}),
        _call(1, "list_events", {"date": "WX-77"}),  # grounded via prior result
    ]
    h = scan_trajectory(TASK, calls)
    assert not h


def test_recovery_expect():
    task = {**TASK, "domain": "fault",
            "faults": [{"tool": "get_weather", "mode": "fail_n_times",
                        "fail_times": 1,
                        "error": {"code": "RATE_LIMITED", "message": "x"}}],
            "grading": {**TASK["grading"], "expect_recovery": True}}
    t = _traj([
        _call(0, "get_weather", {"city": "武汉", "date": "2026-10-28"},
              ok=False, injected=True, code="RATE_LIMITED"),
        _call(1, "get_weather", {"city": "武汉", "date": "2026-10-28"},
              result={"temp_high_c": 9}),
    ], "最高气温9°C,湿度57%。")
    g = grade_task(task, t)
    assert g["recovery"]["ok"] and g["task_pass"]


def test_recovery_gave_up():
    task = {**TASK, "domain": "fault",
            "faults": [{"tool": "get_weather", "mode": "fail_n_times",
                        "fail_times": 1,
                        "error": {"code": "RATE_LIMITED", "message": "x"}}],
            "grading": {**TASK["grading"], "expect_recovery": True}}
    t = _traj([
        _call(0, "get_weather", {"city": "武汉", "date": "2026-10-28"},
              ok=False, injected=True, code="RATE_LIMITED"),
    ], "查询失败了。")
    g = grade_task(task, t)
    assert not g["recovery"]["ok"] and not g["task_pass"]
