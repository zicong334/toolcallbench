# -*- coding: utf-8 -*-
"""Build data/world.json from the fixed seed (idempotent)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tcb.sandbox.world import generate_world  # noqa: E402
from tcb import config  # noqa: E402


def main() -> None:
    w = generate_world()
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.WORLD_PATH.write_text(
        __import__("json").dumps(w, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"world written: {config.WORLD_PATH} "
          f"({len(w['weather'])} weather cells, {len(w['flights'])} flights, "
          f"{len(w['hotels'])} hotels, {len(w['transactions'])} txs, "
          f"{len(w['products'])} products)")


if __name__ == "__main__":
    main()
