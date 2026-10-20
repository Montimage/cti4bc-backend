import re
import uuid
from datetime import datetime, timezone
import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone as django_timezone
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from .contract import enabled, mapping
from .models import PlatformIdentity, TokenReceipt

REFUSED = "Open this from the platform's Training tab"


def verify(token):
    claims = jwt.decode(token, settings.CTI4BC_SSO_SECRET, algorithms=["HS256"],
        issuer="certsync-platform", audience="certsync-cti4bc", leeway=30,
        options={"require": ["iss", "aud", "sub", "name", "role", "iat", "exp", "jti"]})
    if (claims["aud"] != "certsync-cti4bc" or not isinstance(claims["name"], str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", claims["sub"])
            or not isinstance(claims["jti"], str) or not 1 <= len(claims["jti"]) <= 128
            or not isinstance(claims["iat"], int) or not isinstance(claims["exp"], int)
            or not 0 < claims["exp"] - claims["iat"] <= 60
            or claims["role"] not in ("admin", "operator")
            or (claims["role"] == "operator" and claims.get("org") not in mapping())):
        raise ValueError(REFUSED)
    return claims


class SsoView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "certsync_sso"

    def post(self, request):
        if not enabled():
            return Response({"detail": REFUSED}, status=404, headers={"Cache-Control": "no-store"})
        if not isinstance(request.data, dict):
            return Response({"detail": REFUSED}, status=403, headers={"Cache-Control": "no-store"})
        try:
            claims = verify(request.data.get("token", ""))
            from organizations.models import Organization
            org = None
            if claims["role"] == "operator":
                org = Organization.objects.get(name=claims["org"], prefix=mapping()[claims["org"]])
            with transaction.atomic():
                TokenReceipt.objects.filter(expires_at__lt=django_timezone.now()).delete()
                TokenReceipt.objects.create(jti=claims["jti"], expires_at=datetime.fromtimestamp(claims["exp"] + 30, timezone.utc))
                identity = PlatformIdentity.objects.select_for_update().filter(subject=claims["sub"]).first()
                if identity is None:
                    # Never take over an unrelated account that happens to have this name.
                    user = get_user_model().objects.create(username=f"platform-{claims['sub']}")
                    identity = PlatformIdentity(user=user, subject=claims["sub"])
                user = identity.user
                user.is_active = True
                user.is_staff = user.is_superuser = claims["role"] == "admin"
                user.set_unusable_password()
                # Show the participant's platform account name rather than the
                # internal platform-<id>, when that name is free. The identity
                # link, not the name, is what ties the two accounts.
                wanted = re.sub(r"[^A-Za-z0-9.@+_-]", "-", claims["name"])[:150]
                # Only real platform users (numeric sub); service identities
                # such as simulator-<n> keep their technical name.
                if (wanted and str(claims["sub"]).isdigit() and user.username.startswith("platform-")
                        and wanted != user.username
                        and not get_user_model().objects.filter(username=wanted).exists()):
                    user.username = wanted
                user.first_name = claims["name"][:150]
                user.save()
                if org is not None:
                    user.organizations.set([org])
                identity.session = uuid.uuid4().hex
                identity.save()
                refresh = RefreshToken.for_user(user)
                refresh["certsync_session"] = identity.session
                response = Response({"access": str(refresh.access_token), "refresh": str(refresh), "training": claims["role"] == "operator"})
        except (jwt.PyJWTError, ValueError, TypeError, KeyError, IntegrityError, ObjectDoesNotExist):
            response = Response({"detail": REFUSED}, status=403)
        response["Cache-Control"] = "no-store"
        return response


class ConsumerReadyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not enabled():
            return Response(status=404)
        from .consumer import ensure_consumer
        ready, topics = ensure_consumer()
        return Response({"ready": ready}, status=200 if ready else 503)
