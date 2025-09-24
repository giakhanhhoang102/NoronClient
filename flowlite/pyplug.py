# flowlite/pyplug.py
from __future__ import annotations
import json, os, subprocess, sys, time
from typing import Any, Dict, Optional

from .http import _current_ctx

PY_BIN = os.environ.get("PY_PLUGIN_BIN") or sys.executable  # mặc định dùng chính interpreter hiện tại
DEFAULT_TIMEOUT = float(os.environ.get("FL_TASK_TIMEOUT", "30.0"))

_SEARCH_DIRS = [
    os.getcwd(),
    os.path.join(os.getcwd(), "app", "plugins"),
    os.path.join(os.getcwd(), "plugins"),
]

def _resolve_path(file: str) -> str:
    if os.path.isabs(file) and os.path.exists(file):
        return file
    for base in _SEARCH_DIRS:
        cand = os.path.join(base, file)
        if os.path.exists(cand):
            return cand
    raise FileNotFoundError(f"Py plugin not found: {file}; search in: {', '.join(_SEARCH_DIRS)}")

def _merge_env(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    env = dict(os.environ)  # Python plugin thường cần nhiều env hơn
    if extra:
        env.update({str(k): str(v) for k, v in extra.items()})
    return env

def _append_task_trace(kind: str, file: str, args_head: str, ms: float, rc: int, stdout_head: str, stderr_head: str) -> None:
    ctx = _current_ctx()
    tt = (ctx.get("meta") or {}).setdefault("task_trace", [])
    tt.append({
        "kind": kind, "file": file, "ms": round(ms, 3), "rc": rc,
        "args_head": args_head[:256],
        "out_head": stdout_head[:256],
        "err_head": stderr_head[:256],
    })

class _PyNamespace:
    def run(
        self,
        file: str,
        args: Optional[Dict[str, Any]] = None,
        *,
        expect: str = "auto",   # "auto" | "json" | "text"
        timeout: float = DEFAULT_TIMEOUT,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
        py_bin: Optional[str] = None,
        pass_stdin: bool = True
    ) -> Any:
        """
        Chạy plugin Python:
          - expect/json/text tương tự js.run
          - mặc định pass_stdin=True (đẩy JSON vào stdin)
        """
        path = _resolve_path(file)
        argv_args_json = json.dumps(args or {}, ensure_ascii=False)
        argv = [py_bin or PY_BIN, path]

        proc_env = _merge_env(env)
        workdir = cwd or os.path.dirname(path) or os.getcwd()

        t0 = time.time()
        try:
            p = subprocess.run(
                argv,
                input=(argv_args_json.encode("utf-8") if pass_stdin else None),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=proc_env,
                cwd=workdir,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as te:
            dt = time.time() - t0
            _append_task_trace("py", path, argv_args_json, dt, -1, "", f"timeout:{te}")
            raise RuntimeError(f"Py plugin timeout ({timeout}s): {path}") from te
        except Exception as e:
            dt = time.time() - t0
            _append_task_trace("py", path, argv_args_json, dt, -2, "", str(e))
            raise

        dt = time.time() - t0
        out = (p.stdout or b"").decode("utf-8", "replace")
        err = (p.stderr or b"").decode("utf-8", "replace")
        _append_task_trace("py", path, argv_args_json, dt, p.returncode, out, err)

        if p.returncode != 0:
            raise RuntimeError(f"Py plugin failed rc={p.returncode}: {path}\nSTDERR: {err[:512]}")

        if expect == "text":
            return out
        try:
            return json.loads(out)
        except Exception:
            if expect == "json":
                raise RuntimeError(f"Py plugin did not return JSON: {path}\nOUT: {out[:512]}")
            return out  # auto: fallback text

pyplug = _PyNamespace()
