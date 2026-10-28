import hashlib
import logging

from django.core.cache import cache

from .models import Location, LocationView

logger = logging.getLogger(__name__)

VIEW_DEDUP_TTL = 60 * 60


def _viewer_id(request) -> str:
    if request.user.is_authenticated:
        return f"u:{request.user.pk}"
    ip = request.META.get("REMOTE_ADDR", "")
    ua = request.META.get("HTTP_USER_AGENT", "")
    return "a:" + hashlib.sha256(f"{ip}|{ua}".encode()).hexdigest()[:32]


def register_view(request, location: Location) -> bool:
    key = f"locview:{location.pk}:{_viewer_id(request)}"
    try:
        # cache.add -> Redis SET NX EX: atomic "set if absent".
        if not cache.add(key, 1, timeout=VIEW_DEDUP_TTL):
            return False
    except Exception:
        logger.exception("View de-duplication unavailable, view not counted")
        return False

    LocationView.objects.create(
        location=location,
        user=request.user if request.user.is_authenticated else None,
    )
    return True
