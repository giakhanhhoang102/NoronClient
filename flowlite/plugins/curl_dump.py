# flowlite/plugins/curl_dump.py
from __future__ import annotations
import json, os, re, time, uuid
from typing import Any, Dict, List, Tuple

from .base import BasePlugin, register_plugin

SENSITIVE = {"authorization", "cookie", "x-auth-token", "set-cookie", "proxy-authorization"}

def _ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)

def _slug(s: str, maxlen: int = 48) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]+", "-", s or "")
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s[:maxlen] or "req"

def _single_quote(s: str) -> str:
    # POSIX-safe single-quote: ' -> '"'"'
    return "'" + (s or "").replace("'", "'\"'\"'") + "'"

def _pairs_to_dict_multi(pairs: List[Tuple[str, str]]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for k, v in pairs:
        out.setdefault(k, []).append(v)
    return out

def _mask_headers(h: Dict[str, List[str]], extra_mask: List[str], mask_value: str = "***") -> Dict[str, List[str]]:
    masked = {}
    maskset = {*(x.lower() for x in SENSITIVE), *(x.lower() for x in (extra_mask or []))}
    for k, vals in (h or {}).items():
        if k.lower() in maskset:
            masked[k] = [mask_value]
        else:
            masked[k] = vals
    return masked

@register_plugin
class CurlDump(BasePlugin):
    """
    Ghi lệnh cURL tương đương + (tuỳ chọn) dump response.
    - Không sửa request thật; chỉ ghi file phục vụ debug/replay.
    Config:
      dir:            thư mục gốc, mặc định ./logs/curl
      split_by_flow:  nếu True -> ghi vào {dir}/{flow}/
      max_body:       số bytes body response ghi tối đa (mặc định 4096)
      inline_threshold: nếu body request dài hơn ngưỡng này -> ghi ra file .body và dùng --data-binary @file
      include_response: ghi cả response (.resp.txt/.resp.json + .headers)
      mask:           danh sách header cần che thêm (ngoài SENSITIVE mặc định)
    """
    name = "curl_dump"
    priority = 50

    def __init__(self, **config: Any) -> None:
        super().__init__(**config)
        self.base_dir = self.config.get("dir", "./logs/curl")
        self.split_by_flow = bool(self.config.get("split_by_flow", True))
        self.max_body = int(self.config.get("max_body", 4096))
        self.inline_threshold = int(self.config.get("inline_threshold", 2048))
        self.include_response = bool(self.config.get("include_response", True))
        self.extra_mask = list(self.config.get("mask", []))

    def on_request(self, req: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
        method = req.get("method") or "GET"
        url = req.get("url") or ""
        pairs = req.get("headers") or []
        body = req.get("body") or ""
        rid = req.get("id") or f"{int(time.time()*1000)}-{uuid.uuid4().hex[:6]}"
        label = req.get("label") or ""

        # Thư mục
        flow_name = (ctx.get("meta") or {}).get("flow") or "flow"
        root = self.base_dir
        if self.split_by_flow:
            root = os.path.join(root, flow_name)
        _ensure_dir(root)

        # Tạo tên file
        ts = time.strftime("%Y%m%d_%H%M%S")
        host = re.sub(r"^https?://", "", url).split("/")[0]
        path = "/" + "/".join(re.sub(r"^https?://[^/]+", "", url).split("/")[1:]).strip("/")
        slug = _slug(f"{method}_{host}_{path}")
        base = f"{ts}_{slug}_{rid[:6]}"
        f_curl = os.path.join(root, base + ".curl")

        # Chuẩn bị headers đã mask cho string cURL
        hdrs_multi = _pairs_to_dict_multi(pairs)
        masked = _mask_headers(hdrs_multi, self.extra_mask)
        # Giữ thứ tự: đi theo list pairs nhưng value lấy từ masked
        hdr_lines: List[str] = []
        for k, _ in pairs:
            vs = masked.get(k) or masked.get(k.title()) or masked.get(k.lower()) or []
            if not vs:
                continue
            for v in vs:
                hdr_lines.append(f"  -H {_single_quote(f'{k}: {v}')} \\")

        # Body: inline hay file
        body_clause = ""
        f_body = None
        if body:
            if len(body) > self.inline_threshold:
                f_body = os.path.join(root, base + ".body.txt")
                try:
                    with open(f_body, "w", encoding="utf-8") as bf:
                        bf.write(body)
                except Exception:
                    pass
                body_clause = f"  --data-binary @{_single_quote(f_body)}"
            else:
                body_clause = f"  --data-binary {_single_quote(body)}"

        # cURL string
        curl_lines = [
            f"# flow: {flow_name}",
            f"# label: {label}",
            f"# id: {rid}",
            f"# time: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"curl -sS -X {method} {_single_quote(url)} \\",
        ] + hdr_lines

        if body_clause:
            if hdr_lines:
                curl_lines[-1] = curl_lines[-1].rstrip(" \\")  # bỏ dấu \ cuối dòng headers nếu có body riêng
                curl_lines.append(body_clause)
            else:
                curl_lines.append(body_clause)

        curl_txt = "\n".join(curl_lines) + "\n"

        # Ghi file .curl
        try:
            with open(f_curl, "w", encoding="utf-8") as f:
                f.write(curl_txt)
        except Exception:
            pass

        # Lưu index để on_response biết file base
        meta_idx = (ctx.get("meta") or {}).setdefault("_curl_dump_idx", {})
        meta_idx[rid] = {"root": root, "base": base}

        return req  # KHÔNG sửa request thật

    def on_response(self, req: Dict[str, Any], resp: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
        if not self.include_response:
            return resp

        rid = (req or {}).get("id")
        idx = (ctx.get("meta") or {}).get("_curl_dump_idx") or {}
        info = idx.get(rid)
        if not info:
            return resp

        root = info["root"]; base = info["base"]
        f_headers = os.path.join(root, base + ".resp.headers")
        f_resp_txt = os.path.join(root, base + ".resp.txt")
        f_resp_json = os.path.join(root, base + ".resp.json")

        # Headers (mask)
        hdrs: Dict[str, List[str]] = {}
        for k, vals in (resp.get("headers") or {}).items():
            hdrs.setdefault(k, [])
            for v in vals:
                if k.lower() in SENSITIVE:
                    hdrs[k].append("***")
                else:
                    hdrs[k].append(v)

        # Body (truncate)
        body = (resp.get("body") or "")[: self.max_body]

        try:
            with open(f_headers, "w", encoding="utf-8") as fh:
                for k, vals in hdrs.items():
                    for v in vals:
                        fh.write(f"{k}: {v}\n")
        except Exception:
            pass

        # Thử pretty JSON
        is_json = False
        try:
            obj = json.loads(body)
            with open(f_resp_json, "w", encoding="utf-8") as fj:
                json.dump(obj, fj, ensure_ascii=False, indent=2)
            is_json = True
        except Exception:
            pass

        if not is_json:
            try:
                with open(f_resp_txt, "w", encoding="utf-8") as ft:
                    ft.write(body)
            except Exception:
                pass

        return resp
