# flowlite/plugins/base.py
from __future__ import annotations
from typing import Any, Dict, Optional, List

class BasePlugin:
    """
    FlowLite Plugin API v1
    Các hook đều tùy chọn; override thứ bạn cần.
    """
    name: str = "base"
    version: str = "1.0.0"
    priority: int = 100  # số nhỏ chạy trước

    def __init__(self, **config: Any) -> None:
        self.config = config

    # ---- Flow lifecycle ----
    def on_flow_start(self, ctx: Dict[str, Any]) -> None: ...
    def on_flow_end(self, ctx: Dict[str, Any], result: Dict[str, Any], trace: List[dict]) -> None: ...

    # ---- Step lifecycle ----
    def on_step_start(self, step: Dict[str, Any], ctx: Dict[str, Any]) -> None: ...
    def on_step_end(self, step: Dict[str, Any], ctx: Dict[str, Any], response: Optional[Any]) -> None: ...
    def on_error(self, step: Dict[str, Any], ctx: Dict[str, Any], exc: BaseException, trace: List[dict]) -> None: ...

    # ---- HTTP middleware (sẽ dùng ở phần 2 – http.py) ----
    def on_request(self, req: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
        return req
    def on_response(self, req: Dict[str, Any], resp: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
        return resp


# ---- Registry cục bộ cho plugin ----
_LOCAL_REGISTRY: dict[str, type[BasePlugin]] = {}

def register_plugin(cls: type[BasePlugin]) -> type[BasePlugin]:
    """Dùng làm decorator để đăng ký plugin cục bộ."""
    _LOCAL_REGISTRY[cls.name] = cls
    return cls

def resolve_plugin(name_or_cls: Any) -> type[BasePlugin]:
    """Nhận vào tên hoặc class; trả về class plugin."""
    if isinstance(name_or_cls, str):
        if name_or_cls in _LOCAL_REGISTRY:
            return _LOCAL_REGISTRY[name_or_cls]
        raise KeyError(f"Plugin '{name_or_cls}' not found in FlowLite local registry")
    return name_or_cls  # đã là class thì trả nguyên
