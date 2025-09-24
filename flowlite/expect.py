# flowlite/expect.py
from __future__ import annotations
from typing import Any

class _Expect:
    def truthy(self, val: Any, msg: str = "expect.truthy failed") -> None:
        if not val:
            raise AssertionError(msg)

    def eq(self, a: Any, b: Any, msg: str = "") -> None:
        if a != b:
            raise AssertionError(msg or f"expect.eq failed: {a!r} != {b!r}")

    def ge(self, a: Any, b: Any, msg: str = "") -> None:
        if not (a >= b):
            raise AssertionError(msg or f"expect.ge failed: {a!r} < {b!r}")

expect = _Expect()
