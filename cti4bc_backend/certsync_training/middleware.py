"""Narrow training surface; ordinary CTI4BC requests retain their existing views."""
import re
from django.conf import settings
from django.http import JsonResponse
from rest_framework.exceptions import APIException
from .auth import TrainingJWTAuthentication
from .contract import enabled, training_org


# A trainee's view of the system-health page: the state, without the details
# (server addresses, broker host) that the full answer carries.
HEALTH_STATUS_ONLY = object()
_HEALTH_PATHS = ("/api/health/database/", "/api/health/api-server/",
                 "/api/health/external-services/", "/api/health/message-queue/")
_HEALTH_FIELDS = ("status", "response_time", "uptime", "timestamp")


def _status_only(response):
    import json
    try:
        data = json.loads(response.content)
    except (ValueError, AttributeError):
        return JsonResponse({"status": "critical"}, status=response.status_code)
    return JsonResponse({k: data[k] for k in _HEALTH_FIELDS if k in data}, status=response.status_code)


class TrainingBoundaryMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        active = enabled()
        response = self.check(request) if active else None
        if response is HEALTH_STATUS_ONLY:
            response = _status_only(self.get_response(request))
        elif response is None:
            response = self.get_response(request)
        if active:
            response.headers.pop("X-Frame-Options", None)
            origin = getattr(settings, "CERTSYNC_FRAME_ANCESTORS", "https://certsync-platform.montimage.eu")
            if not re.fullmatch(r"https://[A-Za-z0-9.-]+(?::[0-9]+)?", origin):
                origin = "'none'"
            response["Content-Security-Policy"] = f"frame-ancestors {origin}"
        return response

    def check(self, request):
        path = request.path_info.rstrip("/") + "/"
        if path in ("/api/certsync-training/sso/", "/api/token/", "/api/token/refresh/"):
            return None
        if path.startswith(("/admin/", "/static/")):
            return None
        try:
            authenticated = TrainingJWTAuthentication().authenticate(request)
        except APIException:
            return JsonResponse({"detail": "Open this from the platform's Training tab"}, status=403)
        if not authenticated:
            return JsonResponse({"detail": "Open this from the platform's Training tab"}, status=403)
        user, _ = authenticated
        org = training_org(user)
        if org is None:
            return None
        # These lists and detail views already enforce membership. Everything
        # else is denied unless explicitly scoped below, including raw media.
        read = request.method in ("GET", "HEAD", "OPTIONS")
        if read and path in _HEALTH_PATHS:
            return HEALTH_STATUS_ONLY
        if read and path in ("/event/", "/event/share-logs/", "/organizations/", "/api/users/info/", "/strategy/"):
            return None
        if path == "/api/certsync-training/consumer-ready/" and request.method == "POST":
            return None
        match = re.fullmatch(r"/event/(?:share/|update-share-status/|update_risk_profile/|update_playbook/|update_system_reaction/)?(\d+)/", path)
        if match:
            from event.models import Event
            if Event.objects.filter(pk=match[1], organization=org).exists():
                return None
        if path in ("/event/aggregate/", "/event/share-aggregated/") and request.method == "POST":
            # The views scope every source event before returning an aggregate.
            return None
        if read and path.startswith("/misp_servers/"):
            return None
        match = re.fullmatch(r"/event_files/download/(\d+)/", path)
        if read and match:
            from event_files.models import EventAttachment
            if EventAttachment.objects.filter(pk=match[1], event__organization=org).exists():
                return None
        return JsonResponse({"detail": "This function is not available in training."}, status=403)
