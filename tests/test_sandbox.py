# -*- coding: utf-8 -*-
"""Sandbox determinism + tool behaviour + fault injection tests."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tcb import config
from tcb.sandbox.faults import FaultInjector
from tcb.sandbox.tools import dispatch
from tcb.sandbox.world import WorldState, generate_world


def fresh():
    return WorldState(generate_world())


def test_world_deterministic():
    a, b = generate_world(), generate_world()
    assert a == b
    assert a["seed"] == config.WORLD_SEED


def test_world_file_matches_generator():
    w = WorldState.fresh()
    assert w.data["today"] == config.TODAY
    assert w.data["weather"]["武汉|2026-10-28"]["temp_high_c"] == 9


def test_get_weather_ok_and_errors():
    w = fresh()
    ok, r = dispatch(w, "get_weather", {"city": "武汉", "date": "2026-10-28"})
    assert ok and r["temp_high_c"] == 9
    ok, r = dispatch(w, "get_weather", {"city": "亚特兰蒂斯"})
    assert not ok and r["error"]["code"] == "UNKNOWN_CITY"
    ok, r = dispatch(w, "get_weather", {"city": "武汉", "date": "1999-01-01"})
    assert not ok and r["error"]["code"] == "DATE_OUT_OF_RANGE"
    ok, r = dispatch(w, "get_weather", {"city": "武汉", "foo": 1})
    assert not ok and r["error"]["code"] == "UNKNOWN_ARGUMENT"
    ok, r = dispatch(w, "get_weather", {})
    assert not ok and r["error"]["code"] == "INVALID_PARAMS"


def test_unknown_tool():
    ok, r = dispatch(fresh(), "launch_missiles", {})
    assert not ok and r["error"]["code"] == "UNKNOWN_TOOL"


def test_create_event_conflict_then_cancel():
    w = fresh()
    # 2026-10-29 09:00+90 exists (E103) -> 10:00 overlaps
    ok, r = dispatch(w, "create_event", {
        "title": "例会", "date": "2026-10-29",
        "start_time": "10:00", "duration_min": 60})
    assert not ok and r["error"]["code"] == "EVENT_CONFLICT"
    ok, ev = dispatch(w, "create_event", {
        "title": "晚会", "date": "2026-10-29",
        "start_time": "19:00", "duration_min": 60})
    assert ok and ev["event_id"] == "E901"
    ok, r = dispatch(w, "cancel_event", {"event_id": "E901"})
    assert ok and r["status"] == "cancelled"
    ok, r = dispatch(w, "cancel_event", {"event_id": "E901"})
    assert not ok and r["error"]["code"] == "ALREADY_CANCELLED"


def test_order_flow_stock_and_shipped():
    w = fresh()
    ok, r = dispatch(w, "place_order",
                     {"product_id": "P1005", "quantity": 999, "address_id": "A1"})
    assert not ok and r["error"]["code"] == "OUT_OF_STOCK"
    ok, o = dispatch(w, "place_order",
                     {"product_id": "P1005", "quantity": 1, "address_id": "A2"})
    assert ok and o["order_id"] == "O6001" and o["total_cny"] == 599.0
    p = next(x for x in w.data["products"] if x["product_id"] == "P1005")
    assert p["stock"] == 7
    ok, r = dispatch(w, "cancel_order", {"order_id": "O5001"})
    assert not ok and r["error"]["code"] == "ORDER_SHIPPED"
    ok, r = dispatch(w, "cancel_order", {"order_id": "O6001"})
    assert ok and r["status"] == "cancelled"


def test_transactions_and_calculate():
    w = fresh()
    ok, r = dispatch(w, "get_transactions", {"account_id": "ACC001"})
    assert ok and r["count"] == 36
    dining = round(sum(t["amount_cny"] for t in r["transactions"]
                       if t["category"] == "餐饮"), 2)
    assert dining == 241.65
    ok, r = dispatch(w, "calculate", {"expression": "450 + 239*2"})
    assert ok and r["result"] == 928
    ok, r = dispatch(w, "calculate", {"expression": "__import__('os').system('ls')"})
    assert not ok and r["error"]["code"] == "CALC_ERROR"


def test_flight_hotel_booking():
    w = fresh()
    ok, r = dispatch(w, "book_flight", {"flight_id": "FL0008", "passengers": 1})
    assert not ok and r["error"]["code"] == "NO_SEATS"  # seats_left 0
    ok, b = dispatch(w, "book_flight", {"flight_id": "FL0007", "passengers": 1})
    assert ok and b["booking_id"] == "BK7001" and b["total_cny"] == 450
    ok, res = dispatch(w, "book_room", {
        "hotel_id": "HT018", "checkin": "2026-10-29", "nights": 2, "rooms": 1})
    assert ok and res["reservation_id"] == "RS7002" and res["total_cny"] == 478


def test_fault_injector_modes():
    w = fresh()
    inj = FaultInjector([
        {"tool": "get_weather", "mode": "fail_n_times", "fail_times": 1,
         "error": {"code": "RATE_LIMITED", "message": "retry later"}},
        {"tool": "book_room", "mode": "always",
         "error": {"code": "SERVICE_UNAVAILABLE", "message": "down"}},
        {"tool": "search_flights", "mode": "invalid_on",
         "match_args": {"date": "2026-11-05"},
         "error": {"code": "INVALID_PARAMS", "message": "date out of range"}},
    ])
    ok, r = inj.dispatch(w, "get_weather", {"city": "武汉"})
    assert not ok and r["error"]["injected"] and r["error"]["code"] == "RATE_LIMITED"
    ok, r = inj.dispatch(w, "get_weather", {"city": "武汉"})
    assert ok  # second call succeeds
    ok, r = inj.dispatch(w, "book_room", {
        "hotel_id": "HT018", "checkin": "2026-10-29", "nights": 1})
    assert not ok and r["error"]["code"] == "SERVICE_UNAVAILABLE"
    ok, r = inj.dispatch(w, "search_flights",
                         {"origin": "武汉", "dest": "北京", "date": "2026-11-05"})
    assert not ok and r["error"]["injected"]
    ok, r = inj.dispatch(w, "search_flights",
                         {"origin": "武汉", "dest": "北京", "date": "2026-10-29"})
    assert ok


def test_world_isolation_between_runs():
    w1, w2 = fresh(), fresh()
    dispatch(w1, "place_order", {"product_id": "P1005", "quantity": 1,
                                 "address_id": "A1"})
    p2 = next(x for x in w2.data["products"] if x["product_id"] == "P1005")
    assert p2["stock"] == 8  # w2 untouched
