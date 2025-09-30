# app/settings.py
from __future__ import annotations
import os
from dataclasses import dataclass

def _getenv(name: str, default: str = "") -> str:
    v = os.environ.get(name)
    return v if v is not None else default

def _getenv_bool(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.lower() in ("1", "true", "yes", "on")

@dataclass
class Settings:
    # Python gateway auth (header: Authorization)
    GATEWAY_AUTH_TOKEN: str = _getenv("GATEWAY_AUTH_TOKEN", "changeme")

    # TLS-Client microservice config
    TLS_BASE: str = _getenv("TLS_BASE", "http://127.0.0.1:3000")
    TLS_AUTH_HEADER: str = _getenv("TLS_AUTH_HEADER", "X-Auth-Token")
    #TLS_AUTH_HEADER: str = _getenv("TLS_AUTH_HEADER", "x-api-key")
    # Dev helpers
    FLOW_RELOAD: bool = _getenv_bool("FLOW_RELOAD", True)   # reload flow module mỗi request (tiện phát triển)
    DEBUG_TRACE: bool = _getenv_bool("DEBUG_TRACE", True)   # bật trace trong flow mặc định

settings = Settings()
