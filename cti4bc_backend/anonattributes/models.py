from django.db import models
from event.models import Event

class AnonAttributes(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    tag = models.CharField(max_length=100)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    file = models.FileField(upload_to='anon_files/')