# app/flow_loader.py
from __future__ import annotations
import importlib, sys
from types import ModuleType
from typing import Any, Optional
import os
from flowlite import Flow
from app.settings import settings
from flowlite.plugins import CurlDump, MaskCookies

# Cache module để không import lại khi FLOW_RELOAD=False
_FLOW_CACHE: dict[str, ModuleType] = {}

class FlowLoadError(RuntimeError): ...

def load_flow(project: str) -> Flow:
    """
    Tải module flows.{project}, lấy biến 'flow' (kiểu Flow).
    Dev mode (FLOW_RELOAD=True): luôn reload module để nhận code mới.
    """
    mod_name = f"flows.{project}"
    mod: Optional[ModuleType] = None

    if not settings.FLOW_RELOAD and mod_name in _FLOW_CACHE:
        mod = _FLOW_CACHE[mod_name]
    else:
        # Bỏ cache cũ để reload sạch
        if mod_name in sys.modules:
            del sys.modules[mod_name]
        try:
            mod = importlib.import_module(mod_name)
        except Exception as e:
            raise FlowLoadError(f"Cannot import module '{mod_name}': {e}") from e
        if settings.FLOW_RELOAD:
            try:
                mod = importlib.reload(mod)
            except Exception as e:
                raise FlowLoadError(f"Cannot reload module '{mod_name}': {e}") from e
        _FLOW_CACHE[mod_name] = mod

    if not hasattr(mod, "flow"):
        raise FlowLoadError(f"Module '{mod_name}' does not define variable 'flow'")

    flow = getattr(mod, "flow")
    # Auto enable debug plugins theo ENV (tuỳ chọn)

    if os.environ.get("ENABLE_CURL_DUMP", "1") == "1":
        flow.use(CurlDump, dir=os.environ.get("CURL_DUMP_DIR", "./logs/curl"),
                include_response=True, max_body=int(os.environ.get("CURL_DUMP_MAX_BODY", "4096")))

    if os.environ.get("ENABLE_MASK_COOKIES", "1") == "1":
        extra_mask = [x.strip() for x in os.environ.get("MASK_EXTRA", "").split(",") if x.strip()]
        flow.use(MaskCookies, mask=extra_mask)

    if not isinstance(flow, Flow):
        raise FlowLoadError(f"Variable 'flow' in module '{mod_name}' is not a Flow")

    # Chuẩn hoá cấu hình TLS cho flow theo settings server
    flow.tls(base=settings.TLS_BASE, auth_header=settings.TLS_AUTH_HEADER)
    # Bật trace theo settings (nếu flow chưa tự bật)
    if settings.DEBUG_TRACE:
        flow.debug(trace=True)

    return flow
