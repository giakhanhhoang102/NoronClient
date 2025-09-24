# flowlite/js.py
from __future__ import annotations
import json, os, shlex, subprocess, sys, time
from typing import Any, Dict, Optional

# Dùng ctx hiện hành từ http module (đã có trong Phần 2)
from .http import _current_ctx

# Thiết lập mặc định
NODE_BIN = os.environ.get("NODE_BIN", "node")
DEFAULT_TIMEOUT = float(os.environ.get("FL_TASK_TIMEOUT", "30.0"))
# Thư mục tìm plugin nếu path không phải tuyệt đối
_SEARCH_DIRS = [
    os.getcwd(),
    os.path.join(os.getcwd(), "app", "plugins"),
    os.path.join(os.getcwd(), "plugins"),
    os.path.join(os.getcwd(), "flowlite", "plugins"),
]

def _resolve_path(file: str) -> str:
    if os.path.isabs(file) and os.path.exists(file):
        return file
    for base in _SEARCH_DIRS:
        cand = os.path.join(base, file)
        if os.path.exists(cand):
            return cand
    # thử thêm ./app/plugins
    raise FileNotFoundError(f"JS plugin not found: {file}; search in: {', '.join(_SEARCH_DIRS)}")

def _merge_env(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    # White-list cơ bản, tránh kế thừa env quá nhiều nếu cần (giữ PATH/HOME/SHELL...)
    keep = ("PATH", "HOME", "SHELL", "TMPDIR", "SystemRoot")
    env = {k: v for k, v in os.environ.items() if k in keep}
    # Cho phép truyền biến riêng
    if extra:
        env.update({str(k): str(v) for k, v in extra.items()})
    # An toàn cho Node
    env.setdefault("NODE_NO_WARNINGS", "1")
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

class _JSNamespace:
    def run(
        self,
        file: str,
        args: Optional[Dict[str, Any]] = None,
        *,
        expect: str = "auto",   # "auto" | "json" | "text"
        timeout: float = DEFAULT_TIMEOUT,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
        node_bin: Optional[str] = None,
        pass_stdin: bool = False
    ) -> Any:
        """
        Chạy plugin Node:
          - file: tên file (tuyệt đối / tương đối). Nếu tương đối → tìm trong: ./, ./app/plugins, ./plugins
          - args: dict -> truyền vào argv[2] (JSON), hoặc STDIN nếu pass_stdin=True
          - expect: "json" ép parse JSON; "text" trả stdout raw; "auto" thử JSON, fail thì trả text
          - timeout: giây
          - env: biến môi trường bổ sung (hợp nhất với một white-list)
          - cwd: working directory
          - node_bin: override path node (mặc định lấy từ env NODE_BIN hoặc "node")
          - pass_stdin: nếu True → ghi JSON vào stdin thay vì argv
        Trả về: dict (nếu parse JSON OK) hoặc str (stdout).
        Ném RuntimeError khi rc!=0 hoặc lỗi timeout.
        """
        path = _resolve_path(file)
        argv_args_json = json.dumps(args or {}, ensure_ascii=False)
        argv = [node_bin or NODE_BIN, path]
        if not pass_stdin:
            argv.append(argv_args_json)

        # Chuẩn bị env & cwd
        proc_env = _merge_env(env)
        workdir = cwd or os.path.dirname(path) or os.getcwd()

        # Chạy
        t0 = time.time()
        try:
            if pass_stdin:
                p = subprocess.run(
                    argv,
                    input=argv_args_json.encode("utf-8"),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=proc_env,
                    cwd=workdir,
                    timeout=timeout,
                )
            else:
                p = subprocess.run(
                    argv,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=proc_env,
                    cwd=workdir,
                    timeout=timeout,
                )
        except subprocess.TimeoutExpired as te:
            dt = time.time() - t0
            _append_task_trace("js", path, argv_args_json, dt, -1, "", f"timeout:{te}")
            raise RuntimeError(f"JS plugin timeout ({timeout}s): {path}") from te
        except Exception as e:
            dt = time.time() - t0
            _append_task_trace("js", path, argv_args_json, dt, -2, "", str(e))
            raise

        dt = time.time() - t0
        out = (p.stdout or b"").decode("utf-8", "replace")
        err = (p.stderr or b"").decode("utf-8", "replace")
        _append_task_trace("js", path, argv_args_json, dt, p.returncode, out, err)

        if p.returncode != 0:
            raise RuntimeError(f"JS plugin failed rc={p.returncode}: {path}\nSTDERR: {err[:512]}")

        if expect == "text":
            return out
        # "json" or "auto"
        try:
            return json.loads(out)
        except Exception:
            if expect == "json":
                raise RuntimeError(f"JS plugin did not return JSON: {path}\nOUT: {out[:512]}")
            return out  # auto: fallback text

    # Small helpers commonly used in flows
    @staticmethod
    def to_pem_public_key(raw_or_pem: str) -> str:
        s = (raw_or_pem or "").strip()
        if "BEGIN" in s:
            return s
        b64 = "".join(s.split())
        lines = [b64[i:i+64] for i in range(0, len(b64), 64)]
        return "-----BEGIN PUBLIC KEY-----\n" + "\n".join(lines) + "\n-----END PUBLIC KEY-----\n"

js = _JSNamespace()
