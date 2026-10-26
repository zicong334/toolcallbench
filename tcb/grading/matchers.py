# -*- coding: utf-8 -*-
"""Deterministic argument matchers. A matcher spec is {kind: value}."""
from __future__ import annotations

import re
from typing import Any


def _coerce_eq(actual: Any, expected: Any) -> bool:
    if actual == expected:
        return True
    # str/number coercion: 1 == "1", 599.0 == "599"
    sa, se = str(actual).strip(), str(expected).strip()
    if sa == se:
        return True
    try:
        return float(sa) == float(se)
    except (TypeError, ValueError):
        return False


def match(spec: dict, actual: Any) -> bool:
    kind, val = next(iter(spec.items()))
    if kind == "any":
        return True
    if actual is None:
        return False
    if kind == "equals":
        return _coerce_eq(actual, val)
    if kind == "contains":
        return str(val) in str(actual)
    if kind == "in_set":
        return any(_coerce_eq(actual, v) for v in val)
    if kind == "regex":
        return re.search(str(val), str(actual)) is not None
    if kind == "numeric":
        try:
            return abs(float(actual) - float(val["value"])) <= float(val.get("tol", 1e-9))
        except (TypeError, ValueError):
            return False
    raise ValueError(f"unknown matcher kind {kind!r}")
