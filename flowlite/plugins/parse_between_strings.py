from __future__ import annotations
from typing import Any, Dict, Optional

from .base import BasePlugin, register_plugin


def _parse_between(source: str, start: str, end: str, *, include_bounds: bool = False, last: bool = False) -> Optional[str]:
    """
    Lấy chuỗi con nằm giữa `start` và `end` trong `source`.
    - include_bounds: nếu True -> bao gồm cả `start` và `end` trong kết quả
    - last: nếu True -> lấy từ lần xuất hiện CUỐI của `start` trước `end` gần nhất
    Trả về None nếu không tìm thấy.
    """
    if source is None:
        return None
    s = str(source)
    if start is None or end is None:
        return None
    a = str(start)
    b = str(end)

    if a == "" and b == "":
        return s

    if a == "":
        # từ đầu đến trước b
        j = s.find(b)
        if j < 0:
            return None
        return s[: j + (len(b) if include_bounds else 0)]

    if b == "":
        # sau a đến hết
        i = s.rfind(a) if last else s.find(a)
        if i < 0:
            return None
        i2 = i if include_bounds else i + len(a)
        return s[i2:]

    # cả a và b đều có
    i = s.rfind(a) if last else s.find(a)
    if i < 0:
        return None
    j = s.find(b, i + len(a))
    if j < 0:
        return None
    if include_bounds:
        return s[i : j + len(b)]
    return s[i + len(a) : j]


@register_plugin
class ParseBetweenStrings(BasePlugin):
    """
    Plugin tiện ích: trích chuỗi giữa hai mốc.

    Config (tuỳ chọn):
      expose_name: tên hàm gắn vào ctx.vars (mặc định "parse_between")
    Cách dùng trong flow:
      - Bật plugin: flow.use(ParseBetweenStrings)
      - Trong step: ctx.vars.parse_between(text, "have ", " day") → "good"
    """

    name = "parse_between_strings"
    version = "1.0.0"
    priority = 90

    def __init__(self, **config: Any) -> None:
        super().__init__(**config)
        self.expose_name = str(self.config.get("expose_name", "parse_between"))

    # lifecycle
    def on_flow_start(self, ctx: Dict[str, Any]) -> None:
        # gắn tiện ích vào ctx.vars để step gọi trực tiếp
        vars_ns = (ctx.get("vars") or {})
        if self.expose_name and self.expose_name not in vars_ns:
            vars_ns[self.expose_name] = lambda source, start, end, **kw: _parse_between(source, start, end, **kw)
            ctx["vars"] = vars_ns

    # không can thiệp request/response
    # giữ nguyên def on_request/on_response từ BasePlugin (no-op)

    # public API phụ trợ (có thể dùng trực tiếp nếu resolve plugin class)
    @staticmethod
    def parse_between(source: str, start: str, end: str, *, include_bounds: bool = False, last: bool = False) -> Optional[str]:
        return _parse_between(source, start, end, include_bounds=include_bounds, last=last)


