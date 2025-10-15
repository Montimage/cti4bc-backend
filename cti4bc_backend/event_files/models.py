from django.db import models
from event.models import Event
from django.contrib.auth.models import User

def event_attachment_path(instance, filename):
    """
    Dynamically set the upload path for attachments.
    """
    return f'event_attachments/{instance.event.id}/{filename}'

class EventAttachment(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    file = models.FileField(upload_to=event_attachment_path)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    public = models.BooleanField(default=False)

    def __str__(self):
        return f"Attachment for Event {self.event.id} - {self.file.name}"