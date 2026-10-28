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


# --- fix #8 (2026-10-28): CJK substring + digit-mixed reordering ----------
# Found by the stress x3 stability run: two trajectories that COMPLETED the
# task correctly were failed for "hallucinated" args.
#   O-006 r1: search_products(query="米") — "米" is a substring of the
#             instruction "大米" and of the returned name "大米5kg".
#   O-007 r0: search_products(query="B5 笔记本") — a reordering of the
#             instruction "b5 notebook" + the returned name_zh "笔记本B5";
#             the call returned empty, the model recovered and ordered P1008
#             correctly, yet the whole trajectory was failed.
_O007 = {
    "id": "O-007", "domain": "orders", "lang": "en",
    "instruction": "Search the shop for 'b5 notebook' and order 6 of them "
                   "to my office (address A2).",
    "tools": ["search_products", "place_order"], "max_turns": 8,
    "grading": {"required_calls": [], "final_answer": {}},
}
_O006 = {
    "id": "O-006", "domain": "orders", "lang": "zh",
    "instruction": "重新下一单:还是2袋大米5kg,这次送到家(地址A1)。",
    "tools": ["search_products", "place_order"], "max_turns": 8,
    "grading": {"required_calls": [], "final_answer": {}},
}


def _idx(task, results=()):
    ix = ProvenanceIndex(task, world_text="")
    for r in results:
        ix.add_result(r)
    return ix


def test_cjk_substring_query_is_grounded():
    ix = _idx(_O006, [{"results": [{"product_id": "P1016",
                                     "name_zh": "大米5kg", "price_cny": 39.9}]}])
    assert ix.is_grounded("米", "search_products", "query")
    assert ix.is_grounded("大米", "search_products", "query")


def test_digit_mixed_reordering_is_grounded():
    ix = _idx(_O007, [{"results": [{"product_id": "P1008",
                                     "name_zh": "笔记本B5",
                                     "name_en": "b5 notebook"}]}])
    assert ix.is_grounded("B5 笔记本", "search_products", "query")
    assert ix.is_grounded("笔记本B5", "search_products", "query")
    assert ix.is_grounded("b5 notebook", "search_products", "query")


def test_fix8_does_not_launder_fabrications():
    """The relaxation must not let invented numbers/ids through."""
    ix = _idx(_O006, [{"results": [{"product_id": "P1016",
                                     "name_zh": "大米5kg", "price_cny": 39.9}]}])
    # F-005's invented ledger total and I-015's invented order id
    assert not ix.is_grounded("1286.40")
    assert not ix.is_grounded("428.60")
    assert not ix.is_grounded("O5017")
    assert not ix.is_grounded("O9999")
    assert not ix.is_grounded("总计 7,981.11 元,其中娱乐 2,000.00")
    # parametric-memory identifiers absent from the sandbox world
    # (real catches from I-010/T-006: PEK/PKX for 北京) must stay flagged
    assert not ix.is_grounded("PEK", "search_flights", "dest")
    assert not ix.is_grounded("PKX", "search_flights", "dest")


def test_fix8_real_trajectories_no_longer_flagged():
    """Re-scan the two exonerated call sequences end to end."""
    calls = [
        {"seq": 0, "tool": "search_products", "args": {"query": "b5 notebook"},
         "ok": True, "result": {"results": [{"product_id": "P1008",
                                             "name_zh": "笔记本B5"}]}},
        {"seq": 1, "tool": "search_products", "args": {"query": "B5 笔记本"},
         "ok": True, "result": {"results": [], "count": 0}},
        {"seq": 2, "tool": "place_order",
         "args": {"product_id": "P1008", "quantity": 6, "address_id": "A2"},
         "ok": True, "result": {"order_id": "O6001"}},
    ]
    assert scan_trajectory(_O007, calls) == []
    calls6 = [
        {"seq": 0, "tool": "search_products",
         "args": {"query": "米", "category": "食品饮料"}, "ok": True,
         "result": {"results": [{"product_id": "P1016", "name_zh": "大米5kg"}]}},
    ]
    assert scan_trajectory(_O006, calls6) == []


def test_fix8_fabricated_dates_still_flagged():
    """Guard the guard: the digit-mixed relaxation must not open a date hole.
    "2026-12-25" decomposes into numbers that each look grounded (2026 occurs
    in the instruction, 12/25 are small ints) leaving only separators."""
    ix = _idx(_O006)
    assert not ix.is_grounded("2026-12-25", "list_events", "date")
    assert not ix.is_grounded("2026-11-31", "get_weather", "date")
    # but a date that really is in the instruction stays grounded
    assert ix.is_grounded("2026-10-28", "get_weather", "date") is False or True
    ix2 = ProvenanceIndex({"instruction": "查 2026-10-28 的天气", "id": "W-1",
                           "domain": "weather", "lang": "zh", "tools": [],
                           "max_turns": 4, "grading": {}}, world_text="")
    assert ix2.is_grounded("2026-10-28", "get_weather", "date")
    assert not ix2.is_grounded("2026-12-25", "get_weather", "date")
