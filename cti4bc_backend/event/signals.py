from django.db.models.signals import pre_save
from django.dispatch import receiver
from .models import Event, EventShareLog
from django.utils import timezone

@receiver(pre_save, sender=Event)
def handle_event_unshare(sender, instance, **kwargs):
    """
    Signal triggered before saving an Event.
    If the event was shared and is no longer shared, we used to delete all associated share logs,
    but now we keep them for record-keeping purposes.
    """
    # Check if the instance already exists in the database
    try:
        # Get the current state of the event from the database
        old_instance = Event.objects.get(pk=instance.pk)
        
        # If the event was shared but is no longer shared
        if old_instance.shared and not instance.shared:
            # We no longer delete share logs
            # Instead, we simply reset shared_at to None if not already done
            instance.shared_at = None
            
    except Event.DoesNotExist:
        # Event is new, nothing to do
        pass