# -*- coding: utf-8 -*-
"""Sandbox tools: OpenAI function schemas + deterministic dispatch.

dispatch() returns (ok, payload). Errors are structured dicts so the harness
can feed them back to the model verbatim and graders can inspect codes.
Stateful tools mutate the per-run WorldState copy only.
"""
from __future__ import annotations

import re
from typing import Any

from .world import WorldState

# ---------------------------------------------------------------- schemas

def _f(name: str, desc: str, props: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {"type": "object", "properties": props, "required": required},
        },
    }


_STR = {"type": "string"}
_INT = {"type": "integer"}
_NUM = {"type": "number"}

TOOL_SPECS: dict[str, dict] = {
    t["function"]["name"]: t
    for t in [
        _f("get_weather", "Get observed weather for a city on a date (today or next 7 days).",
           {"city": {**_STR, "description": "City name, e.g. 武汉 or Boston"},
            "date": {**_STR, "description": "YYYY-MM-DD; omit for today"}},
           ["city"]),
        _f("get_forecast", "Get a multi-day forecast for a city starting today.",
           {"city": _STR,
            "days": {**_INT, "description": "1-7, default 3"}},
           ["city"]),
        _f("list_events", "List calendar events on a date.",
           {"date": _STR}, ["date"]),
        _f("create_event", "Create a calendar event. Fails with EVENT_CONFLICT if it overlaps an existing active event.",
           {"title": _STR, "date": _STR,
            "start_time": {**_STR, "description": "HH:MM 24h"},
            "duration_min": _INT},
           ["title", "date", "start_time", "duration_min"]),
        _f("cancel_event", "Cancel an active calendar event by id.",
           {"event_id": _STR}, ["event_id"]),
        _f("search_products", "Search the shop catalog. All params optional; combine freely.",
           {"query": {**_STR, "description": "substring match on product name (zh or en)"},
            "category": {**_STR, "enum": ["电子产品", "办公用品", "家居", "食品饮料"]},
            "max_price": _NUM},
           []),
        _f("get_product", "Get full product details by product_id.",
           {"product_id": _STR}, ["product_id"]),
        _f("place_order", "Place an order. Fails on OUT_OF_STOCK / ADDRESS_NOT_FOUND.",
           {"product_id": _STR, "quantity": _INT,
            "address_id": {**_STR, "description": "A1 or A2"}},
           ["product_id", "quantity", "address_id"]),
        _f("cancel_order", "Cancel an order. Shipped orders cannot be cancelled (ORDER_SHIPPED).",
           {"order_id": _STR}, ["order_id"]),
        _f("get_transactions", "List account transactions for a month.",
           {"account_id": _STR,
            "month": {**_STR, "description": "YYYY-MM, default current month 2026-10"}},
           ["account_id"]),
        _f("search_flights", "Search flights by origin, dest, date. Empty list if no flights.",
           {"origin": _STR, "dest": _STR, "date": _STR},
           ["origin", "dest", "date"]),
        _f("book_flight", "Book seats on a flight. Fails on NO_SEATS.",
           {"flight_id": _STR,
            "passengers": {**_INT, "description": "default 1"}},
           ["flight_id"]),
        _f("search_hotels", "Search hotels in a city.",
           {"city": _STR, "checkin": _STR,
            "nights": _INT},
           ["city"]),
        _f("book_room", "Book hotel rooms. Fails on NO_ROOMS.",
           {"hotel_id": _STR, "checkin": _STR,
            "nights": _INT, "rooms": _INT},
           ["hotel_id", "checkin", "nights"]),
        _f("calculate", "Evaluate an arithmetic expression (+ - * / parentheses, decimals).",
           {"expression": _STR}, ["expression"]),
    ]
}

TOOL_NAMES = set(TOOL_SPECS)
_ALLOWED_ARGS = {name: set(spec["function"]["parameters"]["properties"])
                 for name, spec in TOOL_SPECS.items()}
_REQUIRED_ARGS = {name: set(spec["function"]["parameters"]["required"])
                  for name, spec in TOOL_SPECS.items()}


def specs_for(names: list[str]) -> list[dict]:
    missing = [n for n in names if n not in TOOL_SPECS]
    if missing:
        raise KeyError(f"unknown tools in task spec: {missing}")
    return [TOOL_SPECS[n] for n in names]


def _err(code: str, message: str, **extra) -> tuple[bool, dict]:
    return False, {"error": {"code": code, "message": message, **extra}}


def _ok(payload: Any) -> tuple[bool, Any]:
    return True, payload


_EXPR_RE = re.compile(r"^[\d\s\.\+\-\*/\(\)]+$")


def _time_to_min(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


# ---------------------------------------------------------------- dispatch

def dispatch(world: WorldState, name: str, args: dict) -> tuple[bool, Any]:
    if name not in TOOL_SPECS:
        return _err("UNKNOWN_TOOL", f"tool {name!r} does not exist")
    if not isinstance(args, dict):
        return _err("INVALID_PARAMS", "arguments must be a JSON object")
    unknown = set(args) - _ALLOWED_ARGS[name]
    if unknown:
        return _err("UNKNOWN_ARGUMENT",
                    f"unexpected argument(s) {sorted(unknown)} for {name}")
    missing = _REQUIRED_ARGS[name] - set(args)
    if missing:
        return _err("INVALID_PARAMS", f"missing required argument(s): {sorted(missing)}")

    w = world.data
    try:
        return _DISPATCH[name](world, args)
    except (ValueError, TypeError, ZeroDivisionError) as e:
        return _err("INVALID_PARAMS", f"bad argument values: {e}")
    except KeyError as e:
        return _err("INTERNAL_ERROR", f"world key missing: {e}")


def _get_weather(world: WorldState, a: dict):
    w = world.data
    city = a["city"]
    date = a.get("date") or w["today"]
    cities = w["cities_zh"] + w["cities_en"]
    if city not in cities:
        return _err("UNKNOWN_CITY", f"city {city!r} not covered",
                    available_cities=cities)
    if date not in w["dates"]:
        return _err("DATE_OUT_OF_RANGE", f"no data for {date}",
                    available_dates=[w["dates"][0], w["dates"][-1]])
    return _ok(w["weather"][f"{city}|{date}"])


def _get_forecast(world: WorldState, a: dict):
    w = world.data
    city = a["city"]
    cities = w["cities_zh"] + w["cities_en"]
    if city not in cities:
        return _err("UNKNOWN_CITY", f"city {city!r} not covered",
                    available_cities=cities)
    days = int(a.get("days") or 3)
    days = max(1, min(days, len(w["dates"])))
    out = [w["weather"][f"{city}|{d}"] for d in w["dates"][:days]]
    return _ok({"city": city, "days": days, "forecast": out})


def _list_events(world: WorldState, a: dict):
    w = world.data
    date = a["date"]
    if date not in w["dates"]:
        return _err("DATE_OUT_OF_RANGE", f"no data for {date}",
                    available_dates=[w["dates"][0], w["dates"][-1]])
    evs = [e for e in w["events"] if e["date"] == date and e["status"] == "active"]
    return _ok({"date": date, "events": evs, "count": len(evs)})


def _create_event(world: WorldState, a: dict):
    w = world.data
    date = a["date"]
    if date not in w["dates"]:
        return _err("DATE_OUT_OF_RANGE", f"cannot schedule on {date}",
                    available_dates=[w["dates"][0], w["dates"][-1]])
    if not re.match(r"^\d{2}:\d{2}$", a["start_time"]):
        return _err("INVALID_PARAMS", "start_time must be HH:MM 24h")
    start = _time_to_min(a["start_time"])
    end = start + int(a["duration_min"])
    for e in w["events"]:
        if e["date"] == date and e["status"] == "active":
            es = _time_to_min(e["start_time"])
            ee = es + e["duration_min"]
            if start < ee and es < end:
                return _err("EVENT_CONFLICT",
                            f"overlaps existing event {e['event_id']} "
                            f"({e['start_time']}+{e['duration_min']}min)",
                            conflicting_event=e)
    eid = f"E{w['next_event_num']}"
    w["next_event_num"] += 1
    ev = {"event_id": eid, "title_zh": a["title"], "title_en": a["title"],
          "date": date, "start_time": a["start_time"],
          "duration_min": int(a["duration_min"]), "status": "active"}
    w["events"].append(ev)
    return _ok(ev)


def _cancel_event(world: WorldState, a: dict):
    w = world.data
    for e in w["events"]:
        if e["event_id"] == a["event_id"]:
            if e["status"] != "active":
                return _err("ALREADY_CANCELLED", f"{e['event_id']} already cancelled")
            e["status"] = "cancelled"
            return _ok({"event_id": e["event_id"], "status": "cancelled"})
    return _err("EVENT_NOT_FOUND", f"no event {a['event_id']!r}")


def _search_products(world: WorldState, a: dict):
    w = world.data
    q = (a.get("query") or "").strip().lower()
    cat = a.get("category")
    maxp = a.get("max_price")
    out = []
    for p in w["products"]:
        if q and q not in p["name_zh"].lower() and q not in p["name_en"].lower():
            continue
        if cat and p["category"] != cat:
            continue
        if maxp is not None and p["price_cny"] > float(maxp):
            continue
        out.append({"product_id": p["product_id"], "name_zh": p["name_zh"],
                    "name_en": p["name_en"], "price_cny": p["price_cny"],
                    "in_stock": p["stock"] > 0})
    return _ok({"results": out[:10], "count": len(out)})


def _get_product(world: WorldState, a: dict):
    for p in world.data["products"]:
        if p["product_id"] == a["product_id"]:
            return _ok(p)
    return _err("PRODUCT_NOT_FOUND", f"no product {a['product_id']!r}")


def _place_order(world: WorldState, a: dict):
    w = world.data
    p = next((x for x in w["products"] if x["product_id"] == a["product_id"]), None)
    if p is None:
        return _err("PRODUCT_NOT_FOUND", f"no product {a['product_id']!r}")
    qty = int(a["quantity"])
    if qty <= 0:
        return _err("INVALID_PARAMS", "quantity must be >= 1")
    if p["stock"] < qty:
        return _err("OUT_OF_STOCK",
                    f"requested {qty}, only {p['stock']} left",
                    product_id=p["product_id"], stock=p["stock"])
    if not any(x["address_id"] == a["address_id"] for x in w["addresses"]):
        return _err("ADDRESS_NOT_FOUND", f"no address {a['address_id']!r}",
                    available_addresses=[x["address_id"] for x in w["addresses"]])
    p["stock"] -= qty
    oid = f"O{w['next_order_num']}"
    w["next_order_num"] += 1
    order = {"order_id": oid, "product_id": p["product_id"], "quantity": qty,
             "address_id": a["address_id"], "status": "pending",
             "total_cny": round(p["price_cny"] * qty, 2), "placed_at": w["today"]}
    w["orders"].append(order)
    return _ok(order)


def _cancel_order(world: WorldState, a: dict):
    for o in world.data["orders"]:
        if o["order_id"] == a["order_id"]:
            if o["status"] == "shipped":
                return _err("ORDER_SHIPPED",
                            f"{o['order_id']} already shipped, cannot cancel")
            if o["status"] == "cancelled":
                return _err("ALREADY_CANCELLED", f"{o['order_id']} already cancelled")
            o["status"] = "cancelled"
            return _ok({"order_id": o["order_id"], "status": "cancelled"})
    return _err("ORDER_NOT_FOUND", f"no order {a['order_id']!r}")


def _get_transactions(world: WorldState, a: dict):
    w = world.data
    if not any(x["account_id"] == a["account_id"] for x in w["accounts"]):
        return _err("ACCOUNT_NOT_FOUND", f"no account {a['account_id']!r}",
                    available_accounts=[x["account_id"] for x in w["accounts"]])
    month = a.get("month") or "2026-10"
    txs = [t for t in w["transactions"] if t["date"].startswith(month)]
    return _ok({"account_id": a["account_id"], "month": month,
                "transactions": txs, "count": len(txs)})


def _search_flights(world: WorldState, a: dict):
    out = [f for f in world.data["flights"]
           if f["origin"] == a["origin"] and f["dest"] == a["dest"]
           and f["date"] == a["date"]]
    return _ok({"origin": a["origin"], "dest": a["dest"], "date": a["date"],
                "flights": out, "count": len(out)})


def _book_flight(world: WorldState, a: dict):
    w = world.data
    f = next((x for x in w["flights"] if x["flight_id"] == a["flight_id"]), None)
    if f is None:
        return _err("FLIGHT_NOT_FOUND", f"no flight {a['flight_id']!r}")
    pax = int(a.get("passengers") or 1)
    if pax <= 0:
        return _err("INVALID_PARAMS", "passengers must be >= 1")
    if f["seats_left"] < pax:
        return _err("NO_SEATS", f"{f['flight_id']} has {f['seats_left']} seats left",
                    flight_id=f["flight_id"], seats_left=f["seats_left"])
    f["seats_left"] -= pax
    bid = f"BK{w['next_booking_num']}"
    w["next_booking_num"] += 1
    bk = {"booking_id": bid, "flight_id": f["flight_id"], "passengers": pax,
          "total_cny": f["price_cny"] * pax, "status": "confirmed"}
    w["bookings"].append(bk)
    return _ok(bk)


def _search_hotels(world: WorldState, a: dict):
    out = []
    for h in world.data["hotels"]:
        if h["city"] != a["city"]:
            continue
        out.append({**h, "available": h["rooms_left"] > 0})
    return _ok({"city": a["city"], "checkin": a.get("checkin"),
                "nights": a.get("nights") or 1, "hotels": out, "count": len(out)})


def _book_room(world: WorldState, a: dict):
    w = world.data
    h = next((x for x in w["hotels"] if x["hotel_id"] == a["hotel_id"]), None)
    if h is None:
        return _err("HOTEL_NOT_FOUND", f"no hotel {a['hotel_id']!r}")
    nights = int(a["nights"])
    rooms = int(a.get("rooms") or 1)
    if nights <= 0 or rooms <= 0:
        return _err("INVALID_PARAMS", "nights and rooms must be >= 1")
    if h["rooms_left"] < rooms:
        return _err("NO_ROOMS", f"{h['hotel_id']} has {h['rooms_left']} rooms left",
                    hotel_id=h["hotel_id"], rooms_left=h["rooms_left"])
    h["rooms_left"] -= rooms
    rid = f"RS{w['next_booking_num']}"
    w["next_booking_num"] += 1
    res = {"reservation_id": rid, "hotel_id": h["hotel_id"], "checkin": a["checkin"],
           "nights": nights, "rooms": rooms,
           "total_cny": h["price_per_night_cny"] * nights * rooms,
           "status": "confirmed"}
    w["reservations"].append(res)
    return _ok(res)


def _calculate(world: WorldState, a: dict):
    expr = a["expression"].replace(" ", "")
    if not _EXPR_RE.match(expr):
        return _err("CALC_ERROR",
                    "only digits and + - * / ( ) . are allowed",
                    expression=a["expression"])
    try:
        val = eval(expr, {"__builtins__": {}}, {})  # noqa: S307 - sandboxed charset
    except Exception as e:  # noqa: BLE001
        return _err("CALC_ERROR", f"cannot evaluate: {e}")
    return _ok({"expression": a["expression"], "result": val})


_DISPATCH = {
    "get_weather": _get_weather,
    "get_forecast": _get_forecast,
    "list_events": _list_events,
    "create_event": _create_event,
    "cancel_event": _cancel_event,
    "search_products": _search_products,
    "get_product": _get_product,
    "place_order": _place_order,
    "cancel_order": _cancel_order,
    "get_transactions": _get_transactions,
    "search_flights": _search_flights,
    "book_flight": _book_flight,
    "search_hotels": _search_hotels,
    "book_room": _book_room,
    "calculate": _calculate,
}
