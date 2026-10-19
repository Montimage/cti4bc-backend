"""Feature switch, organisation convention and copy-only training routing."""
from copy import deepcopy
from django.conf import settings
from rest_framework.exceptions import PermissionDenied


def enabled():
    secret = getattr(settings, "CTI4BC_SSO_SECRET", "") or ""
    return bool(getattr(settings, "CERTSYNC_TRAINING_ENABLED", False) and len(secret.encode()) >= 32)


def mapping():
    prefix = getattr(settings, "TRAINING_ORG_PREFIX", "TRAIN-")
    count = int(getattr(settings, "TRAINING_ORG_COUNT", 25))
    if not 1 <= count <= 99:
        raise ValueError("TRAINING_ORG_COUNT must be between 1 and 99")
    return {f"{prefix}{i:02d}": f"T{i:02d}" for i in range(1, count + 1)}


def training_org(user):
    if not enabled() or not user.is_authenticated or user.is_superuser:
        return None
    return user.organizations.filter(name__in=mapping()).first()


def validate_targets(user, server_ids, org_ids):
    org = training_org(user)
    if org is None:
        return None
    from misp_servers.models import MISPServer
    url = getattr(settings, "CERTSYNC_PLATFORM_MISP_URL", "").rstrip("/")
    if not url or org_ids or not isinstance(server_ids, list) or not server_ids:
        raise PermissionDenied("Training events may only be shared to the platform MISP.")
    try:
        requested = {int(item) for item in server_ids}
    except (TypeError, ValueError):
        raise PermissionDenied("Invalid MISP destination.")
    servers = MISPServer.objects.filter(id__in=requested, organizations=org).distinct()
    if servers.count() != len(requested) or any(s.url.rstrip("/") != url for s in servers):
        raise PermissionDenied("Training events may only be shared to the platform MISP.")
    return org.name


def addressed_copy(data, org, servers, orgs):
    if not enabled() or org is None:
        return data
    url = getattr(settings, "CERTSYNC_PLATFORM_MISP_URL", "").rstrip("/")
    if org not in mapping() or not url or orgs or not servers or any(s["url"].rstrip("/") != url for s in servers):
        raise PermissionDenied("Training events may only be shared to the platform MISP.")
    copied = deepcopy(data)
    tags = [tag for tag in copied.get("Tag", []) if not tag.get("name", "").startswith("certsync:destination-org=")]
    tags.append({"name": f'certsync:destination-org="{org}"'})
    copied["Tag"] = tags
    return copied


def event_organizations(user):
    org = training_org(user)
    return user.organizations.filter(pk=org.pk) if org else user.organizations.all()
