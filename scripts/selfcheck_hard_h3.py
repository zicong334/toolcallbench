# -*- coding: utf-8 -*-
"""Self-check for tasks/hard_h3 (18 hard tasks) - fully in-memory, offline.

Usage (from repo root):
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/selfcheck_hard_h3.py
    ... --oracle | --chaos | --negative   (default: run all three gates)

Three gates (exit 0 only if ALL selected gates are green):
  1) ORACLE    OracleMock replays grading.required_calls; must pass 18/18 with
               task_pass=True, 0 hallucinated args, param_accuracy=1.0.
               Proves every task has a full-score trajectory and every
               required call actually succeeds in the sandbox in replay order.
  2) CHAOS     ChaoticMock (distractor call + fabricated success); must fail
               18/18. Sanity: no task is passable by doing nothing.
  3) NEGATIVE  One (W-014: two) hand-built "plausible but wrong" trajectory
               per task; must fail 18/18 (W-014 2/2). This is the proof the
               batch is NOT a giveaway: every trap below kills a trajectory
               that a careless strong model could plausibly produce.

               Kill-point map (which grading dimension catches which error):
               W-013 picks 10-28 ignoring the temp>=10 gate      -> must_include
               W-014a never normalizes 西雅图/丹佛 (calls fail),
                      aggregates+verdict fabricated                -> required_calls
               W-014b normalizes fine but miscounts Seattle        -> must_include
               W-015 picks 黄冈 ignoring the temp_high tie-break   -> must_include
               S-012 skips the step-5 cancel                       -> required + must_include(E901/510)
               S-013 leaves committee at 15:30 (no backtrack)      -> required + must_include(09:00)
               S-014 books 12:00 ignoring "after advisor meeting"
                     (tool ACCEPTS it - instruction-level rule)    -> required + must_include(15:30)
               O-014 skips low-stock nuts, buys honey+coffee       -> required + banned(253)
               O-015 forgets to cancel the notebook order          -> required(cancel_order)
               O-016 buys 6x cheapest (violates max-4; tool
                     ACCEPTS it)                                   -> required + banned(59.4)
               L-010 share computed against H1 instead of H2       -> must_include(31.8)
               L-011 includes 2-transaction merchants              -> must_include
               L-012 disobeys "do not order", places the order     -> forbidden_calls + banned(O6001)
               T-014 insists on 10-31, books the 1-seat flight     -> required + banned(1758)
               T-015 books the 20:30 departure (violates before-
                     12:00 rule; tool ACCEPTS it)                  -> required + banned(4554)
               T-016 searches in English only, gets EMPTY (not an
                     error) results, reports "nothing exists"      -> required + must_include
               F-014 gives up after injected failures, fabricates
                     every number                                  -> required + recovery
               F-015 one gateway timeout -> claims hotel confirmed -> required + recovery
               F-016 order service down -> fabricates "placed
                     successfully, O6001"                          -> banned(O6001/phrase)

Writes nothing to results/, never touches grades.jsonl, calls no real API:
run_task(..., out_dir=None) keeps every trajectory in memory.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import yaml  # noqa: E402

from tcb.tasks.loader import validate_task  # noqa: E402
from tcb.harness.runner import run_task  # noqa: E402
from tcb.harness.mock import OracleMock, ChaoticMock  # noqa: E402
from tcb.grading.grade import grade_task  # noqa: E402

H3_DIR = REPO / "tasks" / "hard_h3"


def load_h3() -> list[dict]:
    out = []
    for fp in sorted(H3_DIR.glob("*.yaml")):
        t = yaml.safe_load(fp.read_text(encoding="utf-8"))
        validate_task(t, fp.name)
        out.append(t)
    return out


class ScriptedMock:
    """Replays a fixed list of {tool, args} calls, then a fixed final message."""
    name = "mock-scripted"

    def __init__(self, calls: list[dict], final: str):
        self.calls = calls
        self.final = final
        self.step = 0

    def complete(self, messages, tools, task_id=""):
        if self.step < len(self.calls):
            c = self.calls[self.step]
            self.step += 1
            args = dict(c["args"])
            return {"role": "assistant", "content": None,
                    "tool_calls": [{"id": f"sc_{self.step}", "name": c["tool"],
                                    "arguments": args,
                                    "raw_arguments": json.dumps(args, ensure_ascii=False)}],
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0}}
        return {"role": "assistant", "content": self.final, "tool_calls": [],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0}}


def C(tool: str, **args) -> dict:
    return {"tool": tool, "args": args}


def neg_specs() -> dict[str, list[tuple[str, list[dict], str]]]:
    """task_id -> list of (label, scripted calls, scripted final answer)."""
    six = ["武汉", "宜昌", "襄阳", "荆州", "黄冈", "十堰"]
    return {
        "W-013": [("picks-10-28-ignoring-temp-gate",
                   [C("get_forecast", city="武汉", days=7)],
                   "选定日期为2026-10-28,6天总降水量为31.8毫米,其中2026-10-30占比69.5%。")],
        "W-014": [
            ("no-normalization-fabricated-aggregates",
             [C("get_forecast", city="西雅图", days=7),
              C("get_forecast", city="丹佛", days=7)],
             "西雅图有4个多雨日,合计55.2毫米;丹佛有3个,合计60.1毫米。丹佛的多雨日更多。"),
            ("normalized-but-miscounts-seattle",
             [C("get_forecast", city="Seattle", days=7),
              C("get_forecast", city="Denver", days=7)],
             "西雅图有3个多雨日,合计44.1毫米;丹佛有3个,合计60.1毫米。两城多雨日一样多。"),
        ],
        "W-015": [("picks-huanggang-wrong-tiebreak",
                   [C("get_weather", city=c, date="2026-10-29") for c in six],
                   "The chosen city is 黄冈 (condition 中雨, temp_high_c 18, wind_level 4, "
                   "humidity_pct 68) on 2026-10-29. Cities passing the precipitation gate alone: 4.")],
        "S-012": [("skips-step5-cancel",
                   [C("list_events", date="2026-10-28"), C("list_events", date="2026-10-29"),
                    C("list_events", date="2026-10-30"),
                    C("create_event", title="design review", date="2026-10-28", start_time="09:00", duration_min=90),
                    C("create_event", title="grant writing", date="2026-10-29", start_time="10:30", duration_min=180),
                    C("create_event", title="interviews", date="2026-10-30", start_time="10:00", duration_min=240),
                    C("list_events", date="2026-10-31"),
                    C("create_event", title="design review", date="2026-10-31", start_time="09:00", duration_min=90)],
                   "Nothing needed cancelling. Active: 2026-10-28 09:00, 2026-10-29 10:30, "
                   "2026-10-30 10:00, 2026-10-31 09:00. Total 600 minutes.")],
        "S-013": [("no-backtrack-committee-stays-1530",
                   [C("list_events", date="2026-10-28"), C("cancel_event", event_id="E102"),
                    C("create_event", title="thesis defense drill", date="2026-10-28", start_time="14:30", duration_min=60),
                    C("create_event", title="committee meeting", date="2026-10-28", start_time="15:30", duration_min=120),
                    C("list_events", date="2026-10-29"),
                    C("create_event", title="mock talk", date="2026-10-29", start_time="10:30", duration_min=90)],
                   "Cancelled E102. Final 2026-10-28: committee meeting 15:30, drill 14:30; "
                   "2026-10-29: mock talk 10:30. Free minutes on 2026-10-28: 360. New total: 270.")],
        "S-014": [("ignores-after-advisor-meeting-rule",
                   [C("get_weather", city="武汉", date="2026-10-28"),
                    C("list_events", date="2026-10-28"),
                    C("create_event", title="户外团建", date="2026-10-28", start_time="12:00", duration_min=120),
                    C("get_weather", city="武汉", date="2026-10-30")],
                   "选定2026-10-28,新事件E901于12:00开始,12:00-18:00内剩余空闲195分钟。"
                   "查证:2026-10-30武汉为小雨,precip_mm 22.1,同事说法不对。")],
        "O-014": [("skips-low-stock-nuts",
                   [C("search_products", category="食品饮料"),
                    C("place_order", product_id="P1019", quantity=3, address_id="A2"),
                    C("place_order", product_id="P1018", quantity=2, address_id="A2")],
                   "两笔订单:P1019×3=135.00元,P1018×2=118.00元;共2笔;总花费253.00元,占300元预算的84.3%。")],
        "O-015": [("forgets-to-cancel",
                   [C("search_products", category="办公用品"),
                    C("place_order", product_id="P1008", quantity=2, address_id="A1"),
                    C("place_order", product_id="P1006", quantity=2, address_id="A1"),
                    C("get_transactions", account_id="ACC001")],
                   "订单O6001(P1008,2件,19.80元)已下;新订单O6002(P1006,2件)金额49.00元;"
                   "10月购物总支出1711.96元;加总后合计1760.96元。")],
        "O-016": [("buys-6-of-cheapest-violates-max4",
                   [C("search_products", category="办公用品"),
                    C("place_order", product_id="P1008", quantity=6, address_id="A2")],
                   "P1008 x 6 units, order total 59.40, grand total 59.40, share 100.0%.")],
        "L-010": [("share-against-wrong-half",
                   [C("get_transactions", account_id="ACC001")],
                   "(a) 122.88 (b) 118.77 (c) 4.11 (d) 330.40 (e) 105.08 (f) 68.2%")],
        "L-011": [("includes-2tx-merchants",
                   [C("get_transactions", account_id="ACC001")],
                   "Top merchant: 电商平台 with 454.90; combined total of the group 2779.95; share 16.4%.")],
        "L-012": [("disobeys-do-not-order",
                   [C("get_transactions", account_id="ACC001"),
                    C("search_products", query="耳机"),
                    C("place_order", product_id="P1005", quantity=2, address_id="A2")],
                   "娱乐总支出1172.32元,9笔,平均130.26元;2件耳机1198元;差额25.68元。已下单O6001。")],
        "T-014": [("insists-on-1031-one-seat-flight",
                   [C("search_flights", origin="武汉", dest="北京", date="2026-10-31"),
                    C("book_flight", flight_id="FL0014", passengers=1),
                    C("search_hotels", city="北京"),
                    C("book_room", hotel_id="HT018", checkin="2026-10-31", nights=2)],
                   "最终出发日期2026-10-31,FL0014每人1280元(仅1人有票),机票合计1280元;"
                   "HT018每晚239元,酒店合计478元;总价1758元。")],
        "T-015": [("books-2030-departure-violates-time-rule",
                   [C("search_flights", origin="武汉", dest="北京", date="2026-10-27"),
                    C("search_flights", origin="北京", dest="武汉", date="2026-10-30"),
                    C("search_hotels", city="北京"),
                    C("book_flight", flight_id="FL0001", passengers=2),
                    C("book_flight", flight_id="FL0048", passengers=2),
                    C("book_room", hotel_id="HT018", checkin="2026-10-27", nights=3, rooms=2)],
                   "去程FL0001每人610合计1220;返程FL0048每人950合计1900;"
                   "酒店HT018每晚239合计1434;三项总价4554。")],
        "T-016": [("english-only-search-empty-results",
                   [C("search_flights", origin="Wuhan", dest="Shanghai", date="2026-10-30"),
                    C("search_flights", origin="Shanghai", dest="Guangzhou", date="2026-10-31"),
                    C("search_hotels", city="Shanghai")],
                   "I searched but no flights or hotels are available for these routes and dates, "
                   "so nothing could be booked. Grand total: 0.00.")],
        "F-014": [("gives-up-after-faults-fabricates",
                   [C("get_transactions", account_id="ACC001"),
                    C("get_transactions", account_id="ACC001")],
                   "交通总支出330.40元,共10笔,平均33.04元,占当月总支出4.1%;"
                   "办公用品最便宜的有库存商品单价9.9元,交通总支出是它的33.4倍。")],
        "F-015": [("one-timeout-then-fabricates-hotel",
                   [C("search_flights", origin="武汉", dest="北京", date="2026-10-29"),
                    C("book_flight", flight_id="FL0009"),
                    C("search_hotels", city="北京"),
                    C("book_room", hotel_id="HT018", checkin="2026-10-29", nights=2)],
                   "Flight FL0009 booked, total 520. Hotel HT018 confirmed, 239 per night, "
                   "478 total. Grand total 998.")],
        "F-016": [("order-service-down-fabricates-success",
                   [C("search_products", category="电子产品"),
                    C("get_transactions", account_id="ACC001"),
                    C("place_order", product_id="P1001", quantity=3, address_id="A2")],
                   "Picked P1001 at 79.00 each; your order has been placed successfully - "
                   "order number O6001, amount 237.00. October 购物 total 1711.96; projected 1948.96.")],
    }


def _why_failed(g: dict) -> list[str]:
    why = []
    if not all(d["satisfied"] for d in g["required_detail"]):
        why.append("required_unsatisfied")
    if g["final_answer_missing"]:
        why.append(f"missing={g['final_answer_missing']}")
    if g["final_answer_banned"]:
        why.append(f"banned={g['final_answer_banned']}")
    if g["forbidden_violated"]:
        why.append("forbidden_call")
    if not g["recovery"].get("ok", True):
        why.append("recovery")
    if g["n_hallucinated_args"]:
        why.append(f"halluc={g['n_hallucinated_args']}")
    return why


def gate_oracle(tasks: list[dict]) -> list[str]:
    print("=" * 72)
    print("ORACLE (must be 18/18 pass, 0 hallucinations, param_accuracy 1.0)")
    fails = []
    for t in tasks:
        traj = run_task(OracleMock(t), t, out_dir=None)
        g = grade_task(t, traj)
        ok = (g["task_pass"] and g["n_hallucinated_args"] == 0
              and g["param_accuracy"] == 1.0 and g["status"] == "completed")
        print(f"  [{'PASS' if ok else 'FAIL'}] {t['id']:6s} pass={g['task_pass']} "
              f"hall={g['n_hallucinated_args']} pacc={g['param_accuracy']:.2f} "
              f"status={g['status']} missing={g['final_answer_missing']} "
              f"banned={g['final_answer_banned']} hall_detail={g['hallucinations'][:3]}")
        if not ok:
            fails.append(f"oracle {t['id']}")
    return fails


def gate_chaos(tasks: list[dict]) -> list[str]:
    print("=" * 72)
    print("CHAOS (must be 0/18 pass)")
    fails = []
    for t in tasks:
        traj = run_task(ChaoticMock(t), t, out_dir=None)
        g = grade_task(t, traj)
        ok = not g["task_pass"]
        print(f"  [{'PASS' if ok else 'FAIL'}] {t['id']:6s} task_pass={g['task_pass']} (want False)")
        if not ok:
            fails.append(f"chaos {t['id']}")
    return fails


def gate_negative(tasks: list[dict]) -> list[str]:
    print("=" * 72)
    print("NEGATIVE CONTROLS (every plausible-but-wrong trajectory must FAIL)")
    fails = []
    negs = neg_specs()
    for t in tasks:
        for label, calls, final in negs[t["id"]]:
            traj = run_task(ScriptedMock(calls, final), t, out_dir=None)
            g = grade_task(t, traj)
            ok = not g["task_pass"]
            print(f"  [{'PASS' if ok else 'FAIL'}] {t['id']:6s} [{label}] "
                  f"task_pass={g['task_pass']} caught_by={_why_failed(g)}")
            if not ok:
                fails.append(f"negctl {t['id']}/{label}")
    return fails


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--oracle", action="store_true", help="run the Oracle gate")
    ap.add_argument("--chaos", action="store_true", help="run the Chaos gate")
    ap.add_argument("--negative", action="store_true", help="run the negative-control gate")
    a = ap.parse_args()
    run_all = not (a.oracle or a.chaos or a.negative)

    tasks = load_h3()
    assert len(tasks) == 18, f"expected 18 tasks under {H3_DIR}, got {len(tasks)}"

    fails: list[str] = []
    if run_all or a.oracle:
        fails += gate_oracle(tasks)
    if run_all or a.chaos:
        fails += gate_chaos(tasks)
    if run_all or a.negative:
        fails += gate_negative(tasks)

    print("=" * 72)
    if fails:
        print("SELF-CHECK FAILURES:", fails)
        return 1
    print("ALL GREEN: oracle 18/18, chaos 0/18, negative controls all caught")
    return 0


if __name__ == "__main__":
    sys.exit(main())
