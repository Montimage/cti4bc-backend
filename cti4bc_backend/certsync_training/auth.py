from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from .contract import enabled
from .models import PlatformIdentity


def check_session(user_id, token):
    if enabled():
        identity = PlatformIdentity.objects.filter(user_id=user_id).first()
        if identity and token.get("certsync_session") != identity.session:
            raise AuthenticationFailed("Open this from the platform's Training tab")


class TrainingJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        check_session(user.pk, validated_token)
        return user


class TrainingRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        token = RefreshToken(attrs["refresh"])
        check_session(token["user_id"], token)
        return super().validate(attrs)
