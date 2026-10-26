# -*- coding: utf-8 -*-
"""Regression tests for grader fixes discovered during the first live run:
comma-formatted numbers, calculate.expression exemption, recovery-on-no-fault,
soft grounding for free text."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tcb.grading.grade import _grade_final, grade_task
from tcb.grading.hallucination import ProvenanceIndex, scan_trajectory

TASK = {
    "id": "X-002", "domain": "fault", "lang": "zh",
    "instruction": "把三类账目 240.47、197.06、188.45 加总,报告总计。",
    "tools": ["get_transactions", "calculate"],
    "max_turns": 8,
    "grading": {
        "required_calls": [
            {"tool": "calculate", "args": {}},
        ],
        "final_answer": {"must_include": ["625.58"]},
    },
}


def _call(seq, tool, args, ok=True, injected=False, code=None, result=None):
    return {"seq": seq, "tool": tool, "args": args, "ok": ok,
            "injected": injected, "error_code": code,
            "result": result if result is not None else {"ok": 1}}


def _traj(calls, final, status="completed"):
    return {"task_id": TASK["id"], "status": status, "calls": calls,
            "final_content": final, "n_turns": 2, "wall_seconds": 1,
            "model": "t", "model_id": "t", "run_idx": 0,
            "usage": {"prompt_tokens": 0, "completion_tokens": 0}}


def test_thousands_separator_normalized():
    g = _grade_final({"final_answer": {"must_include": ["7981.11"]}},
                     "总支出:¥7,981.11 CNY")
    assert g["ok"]
    g = _grade_final({"final_answer": {"must_include": ["1040"]}},
                     "Total: ¥1,040")
    assert g["ok"]
    g = _grade_final({"final_answer": {"must_not_include": ["1638"]}},
                     "对比 ¥1,638 方案")
    assert not g["ok"] and g["banned_found"] == ["1638"]


def test_calculate_expression_exempt_from_provenance():
    # 625.58 is a derived intermediate (not in instruction/world/results as such)
    calls = [_call(0, "calculate", {"expression": "240.47+197.06+188.45"},
                   result={"result": 625.58})]
    h = scan_trajectory(TASK, calls)
    assert h == []
    g = grade_task(TASK, _traj(calls, "总计 625.58 元。"))
    assert g["task_pass"]


def test_derived_value_still_caught_outside_calculate():
    calls = [_call(0, "get_transactions", {"account_id": "ACC999"})]
    h = scan_trajectory(TASK, calls)
    assert any(x["value"] == "ACC999" for x in h)


def test_recovery_passes_when_fault_never_fires():
    task = {
        "id": "X-003", "domain": "fault", "lang": "zh",
        "instruction": "订 P1005 一件送到 A2。",
        "tools": ["place_order"], "max_turns": 6,
        "faults": [{"tool": "place_order", "mode": "invalid_on",
                    "match_args": {"address_id": "A1"},
                    "error": {"code": "INVALID_PARAMS", "message": "address rejected"}}],
        "grading": {
            "required_calls": [{"tool": "place_order", "args": {
                "product_id": {"equals": "P1005"},
                "address_id": {"equals": "A2"}}}],
            "expect_recovery": True,
            "final_answer": {"must_include": ["O6001"]},
        },
    }
    calls = [_call(0, "place_order",
                   {"product_id": "P1005", "quantity": 1, "address_id": "A2"},
                   result={"order_id": "O6001"})]
    g = grade_task(task, _traj(calls, "已下单 O6001。"))
    assert g["recovery"]["ok"] and g["task_pass"]


def test_soft_grounding_for_free_text_titles():
    task = {**TASK,
            "instruction": "帮我创建一个标题为项目规划会的日程。",
            "tools": ["create_event"], "domain": "schedule",
            "grading": {"required_calls": [], "final_answer": {}}}
    # rephrase keeps most bigrams from instruction -> grounded
    calls = [_call(0, "create_event",
                   {"title": "项目规划会议", "date": "2026-11-02",
                    "start_time": "10:00", "duration_min": 60})]
    assert scan_trajectory(task, calls) == []
    # fully invented long title -> flagged
    calls = [_call(0, "create_event",
                   {"title": "季度财务审计复盘大会", "date": "2026-11-02",
                    "start_time": "10:00", "duration_min": 60})]
    h = scan_trajectory(task, calls)
    assert any(x["arg"] == "title" for x in h)


def test_forbidden_calls_enforced():
    task = {
        "id": "X-004", "domain": "travel", "lang": "en",
        "instruction": "List flights from Wuhan to Beijing on 2026-10-29 but do NOT book anything.",
        "tools": ["search_flights", "book_flight"], "max_turns": 6,
        "grading": {
            "required_calls": [{"tool": "search_flights", "args": {
                "origin": {"equals": "武汉"}, "dest": {"equals": "北京"},
                "date": {"equals": "2026-10-29"}}}],
            "forbidden_calls": ["book_flight"],
            "final_answer": {"must_include": ["FL0007"]},
        },
    }
    # well-behaved: search only
    calls = [_call(0, "search_flights",
                   {"origin": "武汉", "dest": "北京", "date": "2026-10-29"},
                   result={"flights": [{"flight_id": "FL0007"}]})]
    g = grade_task(task, _traj(calls, "Found FL0007 and others. Not booked."))
    assert g["task_pass"] and not g["forbidden_violated"]
    # violates: books despite instruction
    calls2 = calls + [_call(1, "book_flight", {"flight_id": "FL0007"},
                            result={"booking_id": "BK7001"})]
    g2 = grade_task(task, _traj(calls2, "Booked FL0007."))
    assert not g2["task_pass"] and g2["forbidden_violated"]


def test_hhmm_times_exempt_from_provenance():
    task = {**TASK, "instruction": "在E103结束后安排会议", "domain": "schedule",
            "tools": ["create_event"], "grading": {"required_calls": [], "final_answer": {}}}
    calls = [_call(0, "create_event",
                   {"title": "会议", "date": "2026-11-02",
                    "start_time": "10:30", "duration_min": 60})]
    assert scan_trajectory(task, calls) == []
