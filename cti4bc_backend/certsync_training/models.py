from django.conf import settings
from django.db import models


class TokenReceipt(models.Model):
    jti = models.CharField(max_length=128, primary_key=True)
    expires_at = models.DateTimeField(db_index=True)


class PlatformIdentity(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    subject = models.CharField(max_length=100, unique=True)
    session = models.CharField(max_length=32)
