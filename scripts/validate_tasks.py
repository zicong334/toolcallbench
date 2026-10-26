# -*- coding: utf-8 -*-
"""Validate task YAML files against the schema contract.

Usage: python scripts/validate_tasks.py [paths...]   (default: tasks/)
Exit 0 = all valid; prints per-file errors otherwise.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tcb.tasks.loader import validate_task, TaskError  # noqa: E402
import yaml  # noqa: E402


def main() -> int:
    args = [Path(a) for a in sys.argv[1:]] or [Path(__file__).resolve().parent.parent / "tasks"]
    files: list[Path] = []
    for a in args:
        files.extend(sorted(a.rglob("*.yaml")) if a.is_dir() else [a])
    seen: dict[str, str] = {}
    n_err = 0
    for fp in files:
        try:
            t = yaml.safe_load(fp.read_text(encoding="utf-8"))
            validate_task(t, fp.name)
            if t["id"] in seen:
                raise TaskError(f"duplicate id {t['id']} (also in {seen[t['id']]})")
            seen[t["id"]] = fp.name
        except Exception as e:  # noqa: BLE001
            n_err += 1
            print(f"FAIL {fp}: {e}")
    print(f"validated {len(files)} files, {n_err} errors")
    return 1 if n_err else 0


if __name__ == "__main__":
    sys.exit(main())
