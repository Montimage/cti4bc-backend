from django.db import models
from django.utils.timezone import now

class PublicKey(models.Model):
    name = models.CharField(max_length=100, unique=True)
    file = models.FileField(upload_to='public_keys/')
    parameters = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(default=now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name