# -*- coding: utf-8 -*-
"""Query helper for task authors: compute ground truth from data/world.json.

Usage:
  python scripts/world_query.py weather 武汉 2026-10-28
  python scripts/world_query.py events 2026-10-29
  python scripts/world_query.py product 耳机
  python scripts/world_query.py flights 武汉 北京 2026-10-29
  python scripts/world_query.py hotels 北京
  python scripts/world_query.py txsum ACC001 2026-10 餐饮
  python scripts/world_query.py txlist ACC001 2026-10 [category]
  python scripts/world_query.py order O5001
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tcb import config  # noqa: E402


def main() -> None:
    w = json.loads(config.WORLD_PATH.read_text(encoding="utf-8"))
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "weather":
        city, date = sys.argv[2], sys.argv[3]
        print(json.dumps(w["weather"].get(f"{city}|{date}"), ensure_ascii=False, indent=1))
    elif cmd == "events":
        date = sys.argv[2]
        evs = [e for e in w["events"] if e["date"] == date and e["status"] == "active"]
        print(json.dumps(evs, ensure_ascii=False, indent=1))
    elif cmd == "product":
        q = sys.argv[2].lower()
        hits = [p for p in w["products"]
                if q in p["name_zh"].lower() or q in p["name_en"].lower()
                or q == p["product_id"].lower()]
        print(json.dumps(hits, ensure_ascii=False, indent=1))
    elif cmd == "flights":
        o, d, date = sys.argv[2], sys.argv[3], sys.argv[4]
        fs = sorted([f for f in w["flights"]
                     if f["origin"] == o and f["dest"] == d and f["date"] == date],
                    key=lambda x: x["price_cny"])
        print(json.dumps(fs, ensure_ascii=False, indent=1))
    elif cmd == "hotels":
        city = sys.argv[2]
        hs = sorted([h for h in w["hotels"] if h["city"] == city],
                    key=lambda x: x["price_per_night_cny"])
        print(json.dumps(hs, ensure_ascii=False, indent=1))
    elif cmd == "txsum":
        acc, month = sys.argv[2], sys.argv[3]
        cat = sys.argv[4] if len(sys.argv) > 4 else None
        txs = [t for t in w["transactions"]
               if t["date"].startswith(month) and (cat is None or t["category"] == cat)]
        total = round(sum(t["amount_cny"] for t in txs), 2)
        print(json.dumps({"account": acc, "month": month, "category": cat,
                          "count": len(txs), "total_cny": total}, ensure_ascii=False))
    elif cmd == "txlist":
        acc, month = sys.argv[2], sys.argv[3]
        cat = sys.argv[4] if len(sys.argv) > 4 else None
        txs = [t for t in w["transactions"]
               if t["date"].startswith(month) and (cat is None or t["category"] == cat)]
        print(json.dumps(txs, ensure_ascii=False, indent=1))
    elif cmd == "order":
        oid = sys.argv[2]
        print(json.dumps([o for o in w["orders"] if o["order_id"] == oid],
                         ensure_ascii=False, indent=1))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
