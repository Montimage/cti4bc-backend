from django.db import models
from event.models import Event
from django.contrib.postgres.fields import JSONField

class Playbook(models.Model):
    external_id = models.CharField(max_length=255)
    event = models.ForeignKey(Event, on_delete=models.SET_NULL, null=True, blank=True)
    data = models.JSONField()
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.external_id