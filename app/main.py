# app/main.py
from __future__ import annotations
from typing import Any, Dict, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict

from app.settings import settings
from app.flow_loader import load_flow, FlowLoadError

# ===== Pydantic schemas =====

class ApiSession(BaseModel):
    model_config = ConfigDict(extra="allow")
    profile: Optional[str] = None
    proxy: Optional[str] = None
    reuse: Optional[bool] = None
    sessionId: Optional[str] = None

class ApiOptions(BaseModel):
    model_config = ConfigDict(extra="allow")
    httpVersion: Optional[str] = None    # "h1"|"h2" (flowlite dùng ctx.options.http2 bool nếu muốn)
    randomTLSExtOrder: Optional[bool] = None
    timeoutMs: Optional[int] = None

class ApiRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    data: Dict[str, Any] = Field(default_factory=dict)
    session: ApiSession = Field(default_factory=ApiSession)
    options: ApiOptions = Field(default_factory=ApiOptions)

# ===== FastAPI =====

app = FastAPI(title="FlowLite Gateway", version="0.1.0")

@app.get("/health")
def health():
    return {"ok": True}

# ---- Error handler để trả JSON đồng nhất ----
@app.exception_handler(Exception)
async def unhandled_exc(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"success": False, "project": None, "result": None, "error": str(exc), "details": "", "meta": {}},
    )

# ---- Core endpoint ----
@app.post("/api/{project}")
async def run_project(
    project: str,
    payload: ApiRequest,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    tls_auth_token: Optional[str] = Header(None, alias=settings.TLS_AUTH_HEADER),
):
    # 1) Check Authorization (Python gateway)
    expected = settings.GATEWAY_AUTH_TOKEN or ""
    if not authorization or authorization != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # 2) Load flow
    try:
        flow = load_flow(project)
    except FlowLoadError as fe:
        # (tuỳ chọn) fallback YAML ở đây nếu cần — hiện tại: báo lỗi
        return JSONResponse(
            status_code=404,
            content={"success": False, "project": project, "result": None, "error": str(fe), "details": "", "meta": {}},
        )

    # 3) Chuẩn hoá options: httpVersion -> http2 flag (nếu muốn)
    opts = dict(payload.options.model_dump())
    http_version = (opts.get("httpVersion") or "").lower()
    # lưu cả raw lẫn bool để step tùy chọn sử dụng
    opts["http2"] = True if http_version in ("h2", "http/2", "http2") else False

    # 4) session assemble (giữ nguyên fields — flowlite http builder sẽ tự /init nếu thiếu)
    sess = dict(payload.session.model_dump())

    # 5) data
    data = dict(payload.data)

    # 6) Run flow (sync call; FlowLite hiện là synchronous)
    result = flow.run(
        data=data,
        session=sess,
        options=opts,
        tls_auth_token=tls_auth_token,   # có thể None nếu flow không dùng TLS
        authz=authorization
    )

    # 7) status code theo success/fail
    status = 200 if result.get("success") else 500
    return JSONResponse(status_code=status, content=result)
