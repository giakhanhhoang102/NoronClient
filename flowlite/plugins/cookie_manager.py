from __future__ import annotations
import re
from typing import Any, Dict, List, Tuple

from .base import BasePlugin, register_plugin


def _as_pairs(headers: Any) -> List[Tuple[str, str]]:
    if headers is None:
        return []
    if isinstance(headers, dict):
        return [(k, str(v)) for k, v in headers.items()]
    pairs: List[Tuple[str, str]] = []
    for kv in headers:
        if isinstance(kv, (list, tuple)) and len(kv) == 2:
            pairs.append((str(kv[0]), str(kv[1])))
    return pairs


def _parse_set_cookie(set_cookie: str) -> Tuple[str, str]:
    # Đơn giản: lấy tên=giá trị trước dấu ';'
    # Không xử lý thuộc tính Path/Domain/Expires phức tạp trong phiên bản đầu.
    head = (set_cookie or "").split(";", 1)[0].strip()
    if not head:
        return "", ""
    if "=" not in head:
        return head, ""
    name, value = head.split("=", 1)
    return name.strip(), value.strip()


def _serialize_cookie_jar(jar: Dict[str, str]) -> str:
    # Nối theo chuẩn đơn giản: name=value; name2=value2
    items: List[str] = []
    for k, v in jar.items():
        if k:
            items.append(f"{k}={v}")
    return "; ".join(items)


@register_plugin
class CookieManager(BasePlugin):
    """
    Quản lý cookie xuyên suốt flow.

    - Nhận cookie khởi tạo từ config.initial hoặc ctx.session.cookies sẵn có
    - Gắn header Cookie tự động cho mọi request (requests/tls/systemnet)
    - Cập nhật jar từ resp.cookies và từ header Set-Cookie

    Config:
      - initial: dict hoặc chuỗi cookie (vd: "a=1; b=2") để nạp ban đầu
      - header_name: tên header Cookie (mặc định "Cookie")
      - merge_strategy: "replace" | "keep" (mặc định "replace") khi trùng khóa
    """

    name = "cookie_manager"
    priority = 10  # chạy sớm để các plugin sau nhận header đã có Cookie

    def __init__(self, **config: Any) -> None:
        super().__init__(**config)
        self.header_name = str(config.get("header_name", "Cookie"))
        self.merge_strategy = str(config.get("merge_strategy", "replace")).lower()

    # ---- helpers ----
    @staticmethod
    def _ensure_jar(ctx: Dict[str, Any]) -> Dict[str, str]:
        sess = ctx.setdefault("session", {})
        jar = sess.setdefault("cookies", {})
        if not isinstance(jar, dict):
            jar = {}
            sess["cookies"] = jar
        return jar

    @staticmethod
    def _parse_cookie_string(cookie_str: str) -> Dict[str, str]:
        jar: Dict[str, str] = {}
        if not cookie_str:
            return jar
        for part in cookie_str.split(";"):
            kv = part.strip()
            if not kv:
                continue
            if "=" in kv:
                k, v = kv.split("=", 1)
                jar[k.strip()] = v.strip()
        return jar

    def _merge_into_jar(self, jar: Dict[str, str], new_items: Dict[str, str]) -> None:
        if self.merge_strategy == "keep":
            for k, v in new_items.items():
                jar.setdefault(k, v)
        else:  # replace
            jar.update(new_items)

    # ---- lifecycle ----
    def on_flow_start(self, ctx: Dict[str, Any]) -> None:
        jar = self._ensure_jar(ctx)
        initial = self.config.get("initial")
        init_map: Dict[str, str] = {}
        if isinstance(initial, str):
            init_map = self._parse_cookie_string(initial)
        elif isinstance(initial, dict):
            init_map = {str(k): str(v) for k, v in initial.items()}
        if init_map:
            self._merge_into_jar(jar, init_map)

    # ---- HTTP hooks ----
    def on_request(self, req: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
        jar = self._ensure_jar(ctx)
        headers_pairs = _as_pairs(req.get("headers"))

        # Nếu user đã set Cookie thủ công ở step đầu, hãy merge về jar để giữ xuyên flow
        cookie_header_idx = next((i for i, (k, _) in enumerate(headers_pairs) if k.lower() == self.header_name.lower()), None)
        if cookie_header_idx is not None:
            _, cookie_val = headers_pairs[cookie_header_idx]
            hdr_map = self._parse_cookie_string(cookie_val)
            if hdr_map:
                self._merge_into_jar(jar, hdr_map)

        # Bảo đảm header Cookie phản ánh jar hiện tại
        cookie_value = _serialize_cookie_jar(jar)
        # Xóa các header Cookie cũ (nếu có nhiều)
        headers_pairs = [(k, v) for (k, v) in headers_pairs if k.lower() != self.header_name.lower()]
        if cookie_value:
            headers_pairs.append((self.header_name, cookie_value))

        req["headers"] = headers_pairs
        return req

    def on_response(self, req: Dict[str, Any], resp: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
        jar = self._ensure_jar(ctx)

        # 1) Hợp nhất từ resp.cookies (dict)
        resp_cookies = resp.get("cookies") or {}
        if isinstance(resp_cookies, dict) and resp_cookies:
            self._merge_into_jar(jar, {str(k): str(v) for k, v in resp_cookies.items()})

        # 2) Hợp nhất từ Set-Cookie headers
        headers_multi = resp.get("headers") or {}
        if isinstance(headers_multi, dict):
            set_cookie_values: List[str] = []
            for k, vs in headers_multi.items():
                if k.lower() == "set-cookie":
                    if isinstance(vs, list):
                        set_cookie_values.extend(vs)
                    elif isinstance(vs, str):
                        set_cookie_values.append(vs)
            new_map: Dict[str, str] = {}
            for sc in set_cookie_values:
                name, value = _parse_set_cookie(sc)
                if name:
                    new_map[name] = value
            if new_map:
                self._merge_into_jar(jar, new_map)

        # Không cần sửa body/headers trả về; chỉ cập nhật jar
        return resp


