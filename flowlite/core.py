# flowlite/core.py
from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from .http import _push_ctx, _pop_ctx  # <-- THÊM DÒNG

from .plugins.base import BasePlugin, resolve_plugin

# ========= Exceptions =========

class FlowError(RuntimeError):
    def __init__(self, message: str, step: Optional[str] = None, trace: Optional[List[Dict[str, Any]]] = None):
        super().__init__(message)
        self.step = step
        self.trace = trace or []

# ========= Context =========

class Context(dict):
    """
    Dict với dot-notation: ctx.foo ↔ ctx['foo'].
    Tự bọc dict con thành Context khi truy cập.
    """
    def __getattr__(self, name: str) -> Any:
        try:
            v = self[name]
            if isinstance(v, dict) and not isinstance(v, Context):
                v = Context(v)
                self[name] = v
            return v
        except KeyError:
            raise AttributeError(name)

    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

# ========= Step descriptor =========

@dataclass
class _Step:
    name: str
    func: Callable[[Context], Any]
    retry: int = 0
    backoff: str = "const"     # const|linear|expo
    base_delay: float = 0.0    # giây
    on_error: str = "abort"    # abort|continue
    via: str = "auto"          # auto|tls|requests (dùng ở phần 2)
    meta: Dict[str, Any] = field(default_factory=dict)

# ---- Decorators (dùng ở flows/*.py) ----

def step(name: str, **kwargs: Any):
    """
    @step("ten_step", retry=1, backoff="expo", base_delay=0.5)
    """
    def deco(fn: Callable[[Context], Any]):
        setattr(fn, "__flowlite_step__", _Step(name=name, func=fn, **kwargs))
        return fn
    return deco

def finalize(fn: Callable[[Context], Dict[str, Any]]):
    setattr(fn, "__flowlite_finalize__", True)
    return fn

# ========= Flow =========

class Flow:
    def __init__(self, name: str):
        self.name = name
        self._steps: List[_Step] = []
        self._finalize: Optional[Callable[[Context], Dict[str, Any]]] = None
        self._plugins: List[BasePlugin] = []
        # cấu hình nền (chưa dùng nhiều ở phần 1)
        self._defaults: Dict[str, Any] = dict(profile="chrome_133", http2=True, timeout=60_000)
        self._tls: Dict[str, Any] = dict(base="http://127.0.0.1:3000", auth_header="X-Auth-Token")
        self._debug: Dict[str, Any] = dict(trace=True, body_preview=1024, curl=False)

    # ---- builder cấu hình ----
    def defaults(self, **kwargs: Any) -> "Flow":
        self._defaults.update(kwargs); return self

    def tls(self, **kwargs: Any) -> "Flow":
        self._tls.update(kwargs); return self

    def debug(self, **kwargs: Any) -> "Flow":
        self._debug.update(kwargs); return self

    def use(self, plugin: Any, **config: Any) -> "Flow":
        cls = resolve_plugin(plugin)
        obj = cls(**config)
        self._plugins.append(obj)
        # sắp xếp theo priority (nhỏ chạy trước)
        self._plugins.sort(key=lambda p: getattr(p, "priority", 100))
        return self

    # ---- quét & đăng ký step/finalize trong module flows/*.py ----
    def register(self, module_globals: Dict[str, Any]) -> "Flow":
        for v in module_globals.values():
            st: _Step = getattr(v, "__flowlite_step__", None)
            if st:
                self._steps.append(st)
            if getattr(v, "__flowlite_finalize__", False):
                self._finalize = v
        if self._finalize is None:
            raise AssertionError(f"Flow '{self.name}' missing @finalize")
        return self

    # ---- chạy flow ----
    def run(
        self,
        data: Dict[str, Any] | None = None,
        session: Dict[str, Any] | None = None,
        options: Dict[str, Any] | None = None,
        tls_auth_token: Optional[str] = None,
        authz: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Trả về: { success, project, result, error, details, meta }
        """
        start_ts = time.time()
        ctx = Context()
        ctx.data = Context(data or {})
        ctx.session = Context(session or {})
        ctx.options = Context(options or {})
        ctx.vars = Context({})
        ctx.meta = Context({})
        ctx.meta.flow = self.name 
        ctx._internals = Context({
            "defaults": self._defaults,
            "tls": self._tls,
            "debug": self._debug,
            "tls_auth_token": tls_auth_token,
            "authz": authz,
        })
        ctx._internals["plugins"] = self._plugins      # <--

        trace: List[Dict[str, Any]] = []

        # plugin: flow start
        for p in self._plugins:
            try:
                p.on_flow_start(ctx)
            except Exception as e:
                trace.append({"plugin": p.name, "hook": "on_flow_start", "error": str(e)})

        try:
            # execute steps tuần tự
            for st in self._steps:
                entry = {"name": st.name, "t0": time.time()}
                for p in self._plugins:
                    try:
                        p.on_step_start(st.__dict__, ctx)
                    except Exception as e:
                        trace.append({"plugin": p.name, "hook": "on_step_start", "step": st.name, "error": str(e)})

                attempt = 0
                while True:
                    try:
                        # đảm bảo http builder thấy ctx hiện hành
                        _push_ctx(ctx)
                        try:
                            res = st.func(ctx)
                        finally:
                            _pop_ctx()
                        # step là Python thuần
                        entry["status"] = None
                        entry["t1"] = time.time()
                        for p in self._plugins:
                            try:
                                p.on_step_end(st.__dict__, ctx, res)
                            except Exception as e:
                                trace.append({"plugin": p.name, "hook": "on_step_end", "step": st.name, "error": str(e)})
                        trace.append(entry)
                        break
                    except AssertionError as ae:
                        entry["error"] = f"assert: {ae}"
                        trace.append(entry)
                        for p in self._plugins:
                            try:
                                p.on_error(st.__dict__, ctx, ae, trace)
                            except Exception:
                                pass
                        if st.on_error == "continue":
                            break
                        raise FlowError(f"{st.name}: {ae}", step=st.name, trace=trace)
                    except Exception as e:
                        attempt += 1
                        if attempt <= (st.retry or 0):
                            delay = st.base_delay or 0.0
                            if st.backoff == "linear":
                                delay *= attempt
                            elif st.backoff == "expo":
                                delay *= (2 ** (attempt - 1))
                            if delay > 0:
                                time.sleep(delay)
                            continue
                        entry["error"] = str(e)
                        trace.append(entry)
                        for p in self._plugins:
                            try:
                                p.on_error(st.__dict__, ctx, e, trace)
                            except Exception:
                                pass
                        if st.on_error == "continue":
                            break
                        raise FlowError(f"{st.name}: {e}", step=st.name, trace=trace)

            # finalize
            assert self._finalize is not None
            result = self._finalize(ctx) or {}
            meta = {
                "flow": self.name,
                "duration_s": round(time.time() - start_ts, 3),
                "trace": trace,
            }

            for p in self._plugins:
                try:
                    p.on_flow_end(ctx, result, trace)
                except Exception as e:
                    trace.append({"plugin": p.name, "hook": "on_flow_end", "error": str(e)})

            return {
                "success": True,
                "project": self.name,
                "result": result,
                "error": None,
                "details": None,
                "meta": meta,
            }

        except FlowError as fe:
            return {
                "success": False,
                "project": self.name,
                "result": None,
                "error": str(fe),
                "details": "",
                "meta": {"trace": fe.trace},
            }
        except Exception as e:
            return {
                "success": False,
                "project": self.name,
                "result": None,
                "error": str(e),
                "details": "",
                "meta": {"trace": trace},
            }
