import logging
import os
import socket
from urllib.parse import urlparse
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.core.config import settings

logger = logging.getLogger(__name__)


def resolve_rate_limit_storage_uri() -> str:
    """استخدام Redis عند توفره في الإنتاج لتوحيد العداد بين العمليات، والتراجع الآمن للذاكرة محلياً."""
    explicit = os.getenv("RATE_LIMIT_STORAGE_URI", "").strip()
    if explicit:
        return explicit

    redis_url = (getattr(settings, "REDIS_URL", "") or "").strip()
    if redis_url.startswith(("redis://", "rediss://")):
        parsed = urlparse(redis_url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 6379
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return redis_url
        except OSError:
            pass
    return "memory://"


_storage_uri = resolve_rate_limit_storage_uri()
_display_uri = _storage_uri.split("@")[-1] if "@" in _storage_uri else _storage_uri
logger.info("Rate limiter initialized with storage backend: %s", _display_uri)

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"],
    storage_uri=_storage_uri,
    in_memory_fallback_enabled=True,
)
