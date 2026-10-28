import hashlib
import logging
import time
from urllib.parse import urlencode

from django.core.cache import cache

logger = logging.getLogger(__name__)

VERSION_KEY = "locations:list:version"
LIST_CACHE_TTL = 60 * 5


def _fresh_version() -> int:
    return time.time_ns()


def get_list_version() -> int:
    version = cache.get(VERSION_KEY)
    if version is None:
        cache.add(VERSION_KEY, _fresh_version(), timeout=None)
        version = cache.get(VERSION_KEY)
    return version


# Invalidation = new version in every key; old entries just expire by TTL.
def bump_list_version() -> None:
    try:
        cache.incr(VERSION_KEY)
    except ValueError:
        cache.set(VERSION_KEY, _fresh_version(), timeout=None)
    except Exception:
        logger.exception("Failed to invalidate location list cache")


def list_cache_key(request) -> str:
    query = urlencode(sorted(request.query_params.lists()), doseq=True)
    raw = f"{request.get_host()}{request.path}?{query}"
    digest = hashlib.sha256(raw.encode()).hexdigest()
    return f"locations:list:v{get_list_version()}:{digest}"
