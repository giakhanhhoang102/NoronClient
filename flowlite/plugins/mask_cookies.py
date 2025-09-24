# flowlite/plugins/mask_cookies.py
from __future__ import annotations
import re
from typing import Any, Dict, List, Tuple

from .base import BasePlugin, register_plugin

DEFAULT_MASK = {"authorization", "cookie", "x-auth-token", "set-cookie", "proxy-authorization"}

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

@register_plugin
class MaskCookies(BasePlugin):
    """
    Che dữ liệu nhạy cảm trong TRACE/LOG (không sửa request thật).
    Config:
      mask:      list header tên cần che thêm (ngoài mặc định)
      patterns:  list regex để che trong body request/response khi ghi log (tuỳ chọn)
      mask_value: giá trị thay thế, mặc định '***'
    """
    name = "mask_cookies"
    priority = 40  # chạy trước curl_dump để cURL cũng nhận bản đã che khi ghi file? (chúng ta chỉ log, không sửa req)

    def __init__(self, **config: Any) -> None:
        super().__init__(**config)
        self.mask = set(h.lower() for h in config.get("mask", [])) | DEFAULT_MASK
        self.patterns = [re.compile(p, re.S) for p in config.get("patterns", [])]
        self.mask_value = str(config.get("mask_value", "***"))

    def _redact_headers(self, headers: Any) -> Any:
        pairs = _as_pairs(headers)
        redacted: List[Tuple[str, str]] = []
        for k, v in pairs:
            if k.lower() in self.mask:
                redacted.append((k, self.mask_value))
            else:
                redacted.append((k, v))
        return redacted

    def _redact_text(self, text: str) -> str:
        s = text or ""
        for rx in self.patterns:
            s = rx.sub(self.mask_value, s)
        return s

    def on_request(self, req: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
        # Chỉ ghi log đã che vào meta; KHÔNG trả request đã che về (tránh phá flow).
        entry = {
            "id": req.get("id"),
            "label": req.get("label"),
            "method": req.get("method"),
            "url": req.get("url"),
            "headers": self._redact_headers(req.get("headers")),
        }
        body = req.get("body")
        if isinstance(body, str) and body:
            entry["body_head"] = self._redact_text(body)[:256]
        (ctx.get("meta") or {}).setdefault("mask_log", []).append({"request": entry})
        return req  # không sửa request

    def on_response(self, req: Dict[str, Any], resp: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
        entry = {
            "id": req.get("id"),
            "status": resp.get("status"),
            "headers": [(k, self.mask_value if k.lower() in self.mask else ", ".join(vs)) for k, vs in (resp.get("headers") or {}).items()],
        }
        body = resp.get("body")
        if isinstance(body, str) and body:
            entry["body_head"] = self._redact_text(body)[:256]
        (ctx.get("meta") or {}).setdefault("mask_log", []).append({"response": entry})
        return resp
