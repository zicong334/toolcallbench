# -*- coding: utf-8 -*-
"""Deterministic seeded world generation for the sandbox.

The world is generated once from WORLD_SEED and dumped to data/world.json.
Graders and tools read the same file, so ground truth is reproducible.
All stateful mutations happen on a deep copy per task run.
"""
from __future__ import annotations

import copy
import json
import random
from pathlib import Path

from .. import config

CITIES_ZH = ["武汉", "宜昌", "襄阳", "荆州", "黄冈", "十堰"]
CITIES_EN = ["Boston", "Austin", "Seattle", "Denver", "Chicago", "Phoenix"]
DATES = ["2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30",
         "2026-10-31", "2026-11-01", "2026-11-02"]
CONDITIONS_ZH = ["晴", "多云", "阴", "小雨", "中雨", "雷阵雨"]
CONDITIONS_EN = ["sunny", "cloudy", "overcast", "light rain", "moderate rain", "thunderstorm"]

FLIGHT_ROUTES = [("武汉", "北京"), ("武汉", "上海"), ("武汉", "深圳"),
                 ("北京", "武汉"), ("上海", "广州"), ("深圳", "成都")]


def _gen_weather(rng: random.Random) -> dict:
    weather = {}
    for cities, conds in ((CITIES_ZH, CONDITIONS_ZH), (CITIES_EN, CONDITIONS_EN)):
        for city in cities:
            base = rng.randint(6, 26)
            for i, date in enumerate(DATES):
                temp_high = base + rng.randint(-3, 5) + (2 if i % 2 else 0)
                cond_idx = rng.randrange(len(conds))
                weather[f"{city}|{date}"] = {
                    "city": city,
                    "date": date,
                    "temp_high_c": temp_high,
                    "temp_low_c": temp_high - rng.randint(4, 9),
                    "condition": conds[cond_idx],
                    "wind_level": rng.randint(1, 7),
                    "precip_mm": round(rng.uniform(0, 25), 1) if cond_idx >= 3 else 0.0,
                    "humidity_pct": rng.randint(35, 95),
                }
    return weather


PRODUCT_NAMES = [
    ("无线鼠标", "wireless mouse", "电子产品", 79.0),
    ("机械键盘", "mechanical keyboard", "电子产品", 299.0),
    ("USB-C 扩展坞", "usb-c dock", "电子产品", 189.0),
    ("27寸显示器", "27-inch monitor", "电子产品", 1099.0),
    ("降噪耳机", "noise-cancelling headphones", "电子产品", 599.0),
    ("A4打印纸500张", "a4 paper 500 sheets", "办公用品", 24.5),
    ("中性笔10支装", "gel pens 10-pack", "办公用品", 15.9),
    ("笔记本B5", "b5 notebook", "办公用品", 9.9),
    ("订书机", "stapler", "办公用品", 19.0),
    ("文件收纳架", "file organizer", "办公用品", 45.0),
    ("保温杯500ml", "thermos 500ml", "家居", 89.0),
    ("加湿器", "humidifier", "家居", 129.0),
    ("LED台灯", "led desk lamp", "家居", 99.0),
    ("收纳箱三件套", "storage box set of 3", "家居", 69.0),
    ("拖鞋", "slippers", "家居", 25.0),
    ("大米5kg", "rice 5kg", "食品饮料", 39.9),
    ("橄榄油1L", "olive oil 1L", "食品饮料", 88.0),
    ("挂耳咖啡20包", "drip coffee 20 bags", "食品饮料", 59.0),
    ("蜂蜜500g", "honey 500g", "食品饮料", 45.0),
    ("坚果混合装", "mixed nuts", "食品饮料", 32.0),
]


def _gen_catalog(rng: random.Random) -> dict:
    products = []
    for i, (zh, en, cat, price) in enumerate(PRODUCT_NAMES):
        pid = f"P{1001 + i}"
        stock = rng.choice([0, 0, 3, 8, 15, 40, 100])
        products.append({
            "product_id": pid, "name_zh": zh, "name_en": en,
            "category": cat, "price_cny": price, "stock": stock,
        })
    return {
        "products": products,
        "addresses": [
            {"address_id": "A1", "label_zh": "家", "label_en": "home",
             "detail": "武汉市洪山区珞喻路100号1栋101"},
            {"address_id": "A2", "label_zh": "公司", "label_en": "office",
             "detail": "武汉市东湖高新区高新大道200号A座1502"},
        ],
        "orders": [
            {"order_id": "O5001", "product_id": "P1002", "quantity": 1,
             "address_id": "A1", "status": "shipped", "placed_at": "2026-10-24"},
            {"order_id": "O5002", "product_id": "P1016", "quantity": 2,
             "address_id": "A2", "status": "pending", "placed_at": "2026-10-26"},
        ],
    }


def _gen_events(rng: random.Random) -> list:
    seeds = [
        ("E101", "组会", "group meeting", "2026-10-27", "10:00", 60),
        ("E102", "导师面谈", "advisor meeting", "2026-10-28", "14:30", 45),
        ("E103", "论文讨论", "paper discussion", "2026-10-29", "09:00", 90),
        ("E104", "体检", "physical exam", "2026-10-30", "08:00", 120),
        ("E105", "项目评审", "project review", "2026-10-31", "15:00", 60),
        ("E106", "家庭晚餐", "family dinner", "2026-11-01", "18:00", 90),
    ]
    return [{"event_id": s[0], "title_zh": s[1], "title_en": s[2], "date": s[3],
             "start_time": s[4], "duration_min": s[5], "status": "active"} for s in seeds]


def _gen_flights(rng: random.Random) -> list:
    flights = []
    n = 0
    for origin, dest in FLIGHT_ROUTES:
        for date in DATES[:5]:
            for _ in range(rng.randint(2, 3)):
                n += 1
                hour = rng.randint(7, 21)
                flights.append({
                    "flight_id": f"FL{n:04d}",
                    "flight_no": f"{rng.choice(['MU', 'CZ', 'HU', '3U'])}{rng.randint(1000, 9999)}",
                    "origin": origin, "dest": dest, "date": date,
                    "dep_time": f"{hour:02d}:{rng.choice(['00', '15', '30', '45'])}",
                    "price_cny": rng.choice([380, 450, 520, 610, 780, 950, 1280]),
                    "seats_left": rng.choice([0, 1, 2, 5, 12, 30]),
                })
    return flights


def _gen_hotels(rng: random.Random) -> list:
    hotels = []
    n = 0
    for city in CITIES_ZH[:4] + ["北京", "上海", "深圳"]:
        for brand in ["如家", "汉庭", "全季", "希尔顿欢朋"]:
            n += 1
            hotels.append({
                "hotel_id": f"HT{n:03d}",
                "name": f"{city}{brand}酒店",
                "city": city,
                "price_per_night_cny": rng.choice([189, 239, 319, 429, 559]),
                "rooms_left": rng.choice([0, 1, 3, 8, 20]),
                "rating": round(rng.uniform(3.8, 4.9), 1),
            })
    return hotels


def _gen_transactions(rng: random.Random) -> list:
    cats = ["餐饮", "交通", "购物", "居住", "娱乐"]
    merchants = {
        "餐饮": ["食堂", "兰州拉面", "星巴克", "外卖平台", "火锅店"],
        "交通": ["地铁", "公交", "网约车", "高铁票", "共享单车"],
        "购物": ["超市", "电商平台", "便利店", "水果店", "药店"],
        "居住": ["房租", "水电费", "物业费", "网费"],
        "娱乐": ["电影院", "书店", "健身房", "游戏充值"],
    }
    ranges = {"餐饮": (8, 60), "交通": (2, 90), "购物": (15, 300),
              "居住": (100, 2500), "娱乐": (20, 200)}
    txs = []
    n = 0
    for day in range(1, 27):
        for _ in range(rng.randint(0, 3)):
            n += 1
            cat = rng.choice(cats)
            lo, hi = ranges[cat]
            txs.append({
                "tx_id": f"T{n:04d}",
                "date": f"2026-10-{day:02d}",
                "merchant": rng.choice(merchants[cat]),
                "category": cat,
                "amount_cny": round(rng.uniform(lo, hi), 2),
            })
    return txs


def generate_world(seed: int | None = None) -> dict:
    rng = random.Random(seed if seed is not None else config.WORLD_SEED)
    world = {
        "seed": seed if seed is not None else config.WORLD_SEED,
        "today": config.TODAY,
        "dates": DATES,
        "cities_zh": CITIES_ZH,
        "cities_en": CITIES_EN,
        "weather": _gen_weather(rng),
        "events": _gen_events(rng),
        "next_event_num": 901,
        "flights": _gen_flights(rng),
        "hotels": _gen_hotels(rng),
        "transactions": _gen_transactions(rng),
        "accounts": [{"account_id": "ACC001", "owner": "张三", "currency": "CNY"}],
        "next_order_num": 6001,
        "next_booking_num": 7001,
        "bookings": [],
        "reservations": [],
    }
    world.update(_gen_catalog(rng))
    return world


class WorldState:
    """Mutable per-run copy of the world."""

    def __init__(self, data: dict):
        self.data = data

    @classmethod
    def fresh(cls) -> "WorldState":
        path = Path(config.WORLD_PATH)
        if not path.exists():
            raise FileNotFoundError(f"{path} missing - run scripts/build_world.py")
        return cls(copy.deepcopy(json.loads(path.read_text(encoding="utf-8"))))

    def save_if_missing(self) -> None:
        path = Path(config.WORLD_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(json.dumps(self.data, ensure_ascii=False, indent=1),
                            encoding="utf-8")
