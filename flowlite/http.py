# flowlite/http.py
from __future__ import annotations
import json, time, urllib.parse, uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import requests  # pip install requests

# ===== Helpers =====

SENSITIVE_HDRS = {"authorization", "cookie", "set-cookie", "x-auth-token", "proxy-authorization"}

def _mask_headers(h: Dict[str, List[str]]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for k, v in (h or {}).items():
        if k.lower() in SENSITIVE_HDRS:
            out[k] = ["***"]
        else:
            out[k] = v
    return out

def _as_pairs(headers: Any) -> List[Tuple[str, str]]:
    """
    Accepts:
      - list of [k, v]
      - list of (k, v)
      - dict (order not guaranteed)
    Returns: list[(k, v)] preserving order if already list.
    """
    if headers is None:
        return []
    if isinstance(headers, dict):
        return [(k, str(v)) for k, v in headers.items()]
    pairs: List[Tuple[str, str]] = []
    for kv in headers:
        if not isinstance(kv, (list, tuple)) or len(kv) != 2:
            raise ValueError("headers must be list of [key, value]")
        pairs.append((str(kv[0]), str(kv[1])))
    return pairs

def _pairs_to_dict_multi(pairs: List[Tuple[str, str]]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for k, v in pairs:
        out.setdefault(k, []).append(v)
    return out

def _header_index(pairs: List[Tuple[str, str]], name: str) -> int:
    name = name.lower()
    for i, (k, _) in enumerate(pairs):
        if k.lower() == name:
            return i
    return -1

def _ensure_header(pairs: List[Tuple[str, str]], name: str, value: str, at_front: bool = False) -> None:
    idx = _header_index(pairs, name)
    if idx >= 0:
        if not pairs[idx][1]:  # empty value -> fill
            pairs[idx] = (pairs[idx][0], value)
    else:
        if at_front:
            pairs.insert(0, (name, value))
        else:
            pairs.append((name, value))

def _ensure_identity_encoding(pairs: List[Tuple[str, str]], force_identity: bool = True) -> None:
    if not force_identity:
        return
    idx = _header_index(pairs, "accept-encoding")
    if idx >= 0:
        pairs[idx] = (pairs[idx][0], "identity")
    else:
        pairs.append(("accept-encoding", "identity"))

def _qs_merge(url: str, params: Optional[Dict[str, Any]]) -> str:
    if not params:
        return url
    u = urllib.parse.urlsplit(url)
    q = urllib.parse.parse_qsl(u.query, keep_blank_values=True)
    for k, v in params.items():
        q.append((str(k), str(v)))
    new_q = urllib.parse.urlencode(q)
    return urllib.parse.urlunsplit((u.scheme, u.netloc, u.path, new_q, u.fragment))

# ===== Response =====

@dataclass
class HttpResponse:
    url: str
    status: int
    headers: Dict[str, List[str]]
    body_text: str
    cookies: Dict[str, str]
    used_protocol: Optional[str] = None
    target: Optional[str] = None

    def text(self) -> str:
        return self.body_text

    def json(self) -> Any:
        return json.loads(self.body_text or "null")

    def header(self, name: str) -> List[str]:
        return self.headers.get(name) or self.headers.get(name.title()) or self.headers.get(name.lower()) or []

    def header_one(self, name: str, default: Optional[str] = None) -> Optional[str]:
        vals = self.header(name)
        if not vals:
            return default
        return vals[0]

# ===== Request Builder =====

class _HttpBuilder:
    def __init__(self, ctx: dict, method: str, url: str):
        self.ctx = ctx
        self.method = method.upper()
        self.url = url
        self._headers_pairs: List[Tuple[str, str]] = []
        self._params: Dict[str, Any] = {}
        self._body_json: Optional[Any] = None
        self._body_text: Optional[str] = None
        self._form: Optional[Dict[str, Any]] = None
        self._follow_redirects: Optional[bool] = None
        self._timeout_s: Optional[float] = None
        self._via: str = "auto"   # auto|tls|requests
        self._label: Optional[str] = None
        self._no_proxy: bool = False

    # ---- config ----
    def via_tls(self) -> "_HttpBuilder":
        self._via = "tls"; return self

    def via_requests(self, no_proxy: bool = True) -> "_HttpBuilder":
        self._via = "requests"; self._no_proxy = no_proxy; return self

    def label(self, name: str) -> "_HttpBuilder":
        self._label = name; return self

    def headers(self, headers: Any) -> "_HttpBuilder":
        self._headers_pairs.extend(_as_pairs(headers)); return self

    def header(self, name: str, value: str) -> "_HttpBuilder":
        self._headers_pairs.append((name, value)); return self

    def accept(self, value: str) -> "_HttpBuilder":
        return self.header("accept", value)

    def accept_encoding(self, value: str) -> "_HttpBuilder":
        return self.header("accept-encoding", value)

    def user_agent(self, value: str) -> "_HttpBuilder":
        return self.header("user-agent", value)

    def referer(self, value: str) -> "_HttpBuilder":
        return self.header("referer", value)

    def content_type(self, value: str) -> "_HttpBuilder":
        return self.header("content-type", value)

    def params(self, d: Dict[str, Any]) -> "_HttpBuilder":
        self._params.update(d or {}); return self

    def json(self, obj: Any) -> "_HttpBuilder":
        self._body_json = obj; self._form = None; self._body_text = None
        self.content_type("application/json")
        return self

    def form(self, d: Dict[str, Any]) -> "_HttpBuilder":
        self._form = d or {}; self._body_json = None; self._body_text = None
        self.content_type("application/x-www-form-urlencoded; charset=UTF-8")
        return self

    def body_text(self, s: str) -> "_HttpBuilder":
        self._body_text = s; self._body_json = None; self._form = None
        return self

    def follow_redirects(self, flag: bool) -> "_HttpBuilder":
        self._follow_redirects = flag; return self

    def timeout(self, seconds: float) -> "_HttpBuilder":
        self._timeout_s = seconds; return self

    # ---- send ----
    def send(self) -> HttpResponse:
        # Build final URL (+ params)
        req_id = f"{int(time.time()*1000)}-{uuid.uuid4().hex[:6]}"   # <--
        url = _qs_merge(self.url, self._params)

        # Prepare headers (pair list)
        pairs = list(self._headers_pairs)

        # Defaults from ctx._internals / ctx.options / ctx.vars
        debug_cfg = (self.ctx.get("_internals") or {}).get("debug", {}) or {}
        force_identity = bool(debug_cfg.get("force_identity", True))
        _ensure_identity_encoding(pairs, force_identity=force_identity)

        # Ensure Host + UA
        u = urllib.parse.urlsplit(url)
        host = u.netloc
        if host:
            _ensure_header(pairs, "host", host, at_front=True)
        # UA fallback
        ua_default = (self.ctx.get("vars") or {}).get("ua") or "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/133 Safari/537.36"
        idx_ua = _header_index(pairs, "user-agent")
        if idx_ua < 0 or not pairs[idx_ua][1].strip():
            _ensure_header(pairs, "user-agent", ua_default)

        # Body build
        body_str: Optional[str] = None
        if self._body_json is not None:
            body_str = json.dumps(self._body_json, ensure_ascii=False)
        elif self._form is not None:
            body_str = urllib.parse.urlencode(self._form)
        elif self._body_text is not None:
            body_str = self._body_text

        # Ensure Content-Length for methods có body (đặc biệt khi via_tls)
        if self.method in {"POST", "PUT", "PATCH", "DELETE"}:
            blen = len((body_str or "").encode("utf-8"))
            _ensure_header(pairs, "content-length", str(blen))

        # Decide route
        route = self._via
        if route == "auto":
            # nếu đã có TLS session id trong ctx → mặc định ưu tiên TLS
            route = "tls" if (self.ctx.get("session") or {}).get("id") else "requests"

        # Trace request skeleton
        req_trace = {
            "t": round(time.time(), 3),
            "label": self._label,
            "method": self.method,
            "url": url,
            "via": route,
            "headers": _mask_headers(_pairs_to_dict_multi(pairs)),
            "body_len": len(body_str or ""),
            "body_head": (body_str or "")[:256],
            "rid": req_id
        }

        # Run through plugin on_request
        for p in (self.ctx.get("_internals") or {}).get("plugins", []):
            try:
                mod_req = p.on_request({
                    "id": req_id,
                    "label": self._label,
                    "method": self.method,
                    "url": url,
                    "headers": pairs,
                    "body": body_str,
                    "via": route
                }, self.ctx)

                if isinstance(mod_req, dict):
                    # allow plugin to modify
                    pairs = _as_pairs(mod_req.get("headers", pairs))
                    url = mod_req.get("url", url)
                    body_str = mod_req.get("body", body_str)
                    route = mod_req.get("via", route)
            except Exception as e:
                # do not break flow
                req_trace.setdefault("plugin_errors", []).append({"plugin": getattr(p, "name", "?"), "hook": "on_request", "err": str(e)})

        # Send
        if route == "tls":
            resp = self._send_via_tls(url, pairs, body_str)
        else:
            resp = self._send_via_requests(url, pairs, body_str)

        # Plugin on_response
        for p in (self.ctx.get("_internals") or {}).get("plugins", []):
            try:
                new = p.on_response(
                    {"id": req_id, "label": self._label, "method": self.method, "url": url, "headers": pairs, "body": body_str, "via": route},
                    {"status": resp.status, "headers": resp.headers, "body": resp.body_text, "cookies": resp.cookies},
                    self.ctx
                )

                if isinstance(new, dict):
                    # allow plugin to modify response body/headers if needed
                    if "body" in new:
                        resp.body_text = str(new["body"])
                    if "headers" in new:
                        resp.headers = dict(new["headers"])
            except Exception as e:
                req_trace.setdefault("plugin_errors", []).append({"plugin": getattr(p, "name", "?"), "hook": "on_response", "err": str(e)})

        # Append http trace
        http_trace = (self.ctx.get("meta") or {}).setdefault("http_trace", [])
        http_trace.append({
            **req_trace,
            "status": resp.status,
            "resp_headers": _mask_headers(resp.headers),
            "resp_len": len(resp.body_text or ""),
            "resp_head": (resp.body_text or "")[:512],
        })

        return resp

    # ---- send via TLS (/forward) ----
    def _send_via_tls(self, url: str, pairs: List[Tuple[str, str]], body_str: Optional[str]) -> HttpResponse:
        # Ensure we have sessionId; if không có, gọi /init
        session_id = (self.ctx.get("session") or {}).get("id")
        if not session_id:
            session_id = _ensure_tls_session(self.ctx)
            self.ctx.setdefault("session", {})["id"] = session_id

        tls_cfg = (self.ctx.get("_internals") or {}).get("tls", {}) or {}
        base = tls_cfg.get("base") or "http://127.0.0.1:3000"
        token_header = tls_cfg.get("auth_header") or "X-Auth-Token"
        tls_token = (self.ctx.get("_internals") or {}).get("tls_auth_token")
        if not tls_token:
            raise RuntimeError("TLS auth token is required for via_tls requests")

        # Build forward payload
        payload = {
            "sessionId": session_id,
            "uri": url,
            "method": self.method,
            "body": body_str or "",
            "headers": pairs,  # keep order
        }
        r = requests.post(f"{base}/forward",
                          headers={token_header: tls_token, "content-type": "application/json"},
                          data=json.dumps(payload).encode("utf-8"),
                          timeout=(self._timeout_s or 60.0))
        r.raise_for_status()
        j = r.json()

        # Normalize
        status = int(j.get("status", 0))
        body_text = j.get("body") or ""
        headers_raw = j.get("headers") or {}
        # convert values to list[str]
        headers = {k: (v if isinstance(v, list) else [str(v)]) for k, v in headers_raw.items()}
        cookies = j.get("cookies") or {}
        used_protocol = j.get("usedProtocol")
        target = j.get("target") or url

        return HttpResponse(url=target, status=status, headers=headers, body_text=body_text, cookies=cookies, used_protocol=used_protocol, target=target)

    # ---- send via requests (direct) ----
    def _send_via_requests(self, url: str, pairs: List[Tuple[str, str]], body_str: Optional[str]) -> HttpResponse:
        headers = {k: v for k, v in pairs}
        timeout = self._timeout_s or 60.0

        # Redirects
        allow_redirects = True if self._follow_redirects is None else bool(self._follow_redirects)

        # Proxies: nếu no_proxy=True -> không dùng proxies (requests mặc định tôn trọng env)
        proxies = {} if self._no_proxy else None

        data = None
        json_payload = None
        if self._body_json is not None:
            json_payload = self._body_json
        elif self._form is not None:
            data = urllib.parse.urlencode(self._form)
        elif self._body_text is not None:
            data = self._body_text

        resp = requests.request(self.method, url, headers=headers, data=data, json=json_payload,
                                timeout=timeout, allow_redirects=allow_redirects, proxies=proxies)

        # Normalize
        status = resp.status_code
        # headers multi
        hdrs_multi: Dict[str, List[str]] = {}
        for k, v in resp.headers.items():
            hdrs_multi.setdefault(k, []).append(v)
        # text (requests sẽ decode gzip/br)
        txt = resp.text or ""
        # cookies
        cdict = {c.name: c.value for c in resp.cookies}
        # protocol (requests không expose dễ, để None)
        return HttpResponse(url=str(resp.url), status=status, headers=hdrs_multi, body_text=txt, cookies=cdict, used_protocol=None, target=str(resp.url))


# ===== Public API =====

class _HttpNamespace:
    def get(self, url: str) -> _HttpBuilder:
        return _HttpBuilder(_current_ctx(), "GET", url)

    def post(self, url: str) -> _HttpBuilder:
        return _HttpBuilder(_current_ctx(), "POST", url)

    def patch(self, url: str) -> _HttpBuilder:
        return _HttpBuilder(_current_ctx(), "PATCH", url)

    # helpers
    @staticmethod
    def urlencode(s: str) -> str:
        return urllib.parse.quote_plus(str(s))

    @staticmethod
    def sha256_hex(s: str) -> str:
        import hashlib
        return hashlib.sha256(str(s).encode("utf-8")).hexdigest()

    @staticmethod
    def re(pattern: str, text: str, group: int = 0) -> Optional[str]:
        import re
        m = re.search(pattern, text or "", re.S)
        return m.group(group) if m else None


# ---- ctx provider (set by core at runtime) ----
# Để đơn giản, ta dùng biến thread-local nhẹ; skeleton 1 luồng nên tĩnh cũng được.
_CTX_STACK: List[dict] = []

def _current_ctx() -> dict:
    if not _CTX_STACK:
        raise RuntimeError("http.* used outside flow.run() context")
    return _CTX_STACK[-1]

# Hàm nội bộ core sẽ dùng để gán ctx khi run step (Phần 2b – ở dưới)
def _push_ctx(ctx: dict) -> None:
    _CTX_STACK.append(ctx)

def _pop_ctx() -> None:
    if _CTX_STACK:
        _CTX_STACK.pop()

# ===== TLS helper: init session nếu thiếu =====

def _ensure_tls_session(ctx: dict) -> str:
    """
    Gọi /init để lấy sessionId khi ctx.session.id chưa có.
    Dựa trên defaults/tls trong ctx._internals.
    """
    tls_cfg = (ctx.get("_internals") or {}).get("tls", {}) or {}
    base = tls_cfg.get("base") or "http://127.0.0.1:3000"
    token_header = tls_cfg.get("auth_header") or "X-Auth-Token"
    tls_token = (ctx.get("_internals") or {}).get("tls_auth_token")
    if not tls_token:
        raise RuntimeError("TLS auth token is required for /init")

    defaults = (ctx.get("_internals") or {}).get("defaults", {}) or {}
    profile = (ctx.get("session") or {}).get("profile") or defaults.get("profile", "chrome_133")
    proxy = (ctx.get("session") or {}).get("proxy") or defaults.get("proxy", "")
    http2 = bool((ctx.get("options") or {}).get("http2") or defaults.get("http2", True))
    random_order = bool(defaults.get("randomTLSExtOrder", True))

    payload = {
        "tlsClientIdentifier": profile,
        "proxyUrl": proxy or "",
        "followRedirects": True,
        "withRandomTLSExtensionOrder": random_order
    }
    # POST /init
    r = requests.post(f"{base}/init",
                      headers={token_header: tls_token, "content-type": "application/json"},
                      data=json.dumps(payload).encode("utf-8"),
                      timeout=30.0)
    r.raise_for_status()
    j = r.json()
    if not j.get("success"):
        raise RuntimeError(f"TLS /init failed: {j}")
    sid = j.get("sessionId")
    if not sid:
        raise RuntimeError("TLS /init returned no sessionId")
    return sid


# public namespace
http = _HttpNamespace()
