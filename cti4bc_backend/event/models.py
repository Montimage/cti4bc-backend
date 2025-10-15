from django.db import models
from organizations.models import Organization
from django.contrib.auth import get_user_model

class Event(models.Model):
    """
    Event model to store event-related data.
    Attributes:
        external_id (CharField): An optional external identifier for the event.
        data (JSONField): A JSON field to store event data.
        shared (BooleanField): A flag indicating whether the event is shared. Defaults to False.
        shared_at (DateTimeField): The timestamp when the event was shared.
        organization (ForeignKey): A reference to the associated organization.
        arrival_time (DateTimeField): An optional timestamp for when the event arrived.
        timeliness (DurationField): An optional duration representing the timeliness of the event. (Time since the event arrives until it is shared)
        extension_time (DurationField): An optional duration for the extension time of the event. (Enrichment time with data from other DYNABIC components)
        anon_time (DurationField): An optional duration for the anonymization time of the event.
        sharing_speed (DurationField): An optional duration for the speed of sharing the event. (Connection time to the MISP server)
    """
    external_id = models.CharField(max_length=255, null=True, blank=True)
    data = models.JSONField()
    shared = models.BooleanField(default=False)
    shared_at = models.DateTimeField(null=True, blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    arrival_time = models.DateTimeField(null=True, blank=True)
    timeliness = models.DurationField(null=True, blank=True)
    extension_time = models.DurationField(null=True, blank=True)
    anon_time = models.DurationField(null=True, blank=True)
    sharing_speed = models.DurationField(null=True, blank=True)

class EventShareLog(models.Model):
    """
    EventShareLog model to track event sharing history.
    Attributes:
        event (ForeignKey): A reference to the shared event.
        shared_by (ForeignKey): A reference to the user who shared the event.
        shared_at (DateTimeField): The timestamp when the event was shared.
        data (JSONField): The complete event data as it was at the time of sharing, including all attributes and modifications.
            This field now also includes 'sharing_results' which contains details about the MISP servers 
            to which the event was shared (server IDs, names, success status, and messages).
        deleted_by (ForeignKey): A reference to the user who deleted the share log.
        deleted_at (DateTimeField): The timestamp when the share log was deleted.
    """
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='share_logs')
    shared_by = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True, related_name='shared_logs')
    shared_at = models.DateTimeField()  
    data = models.JSONField()
    deleted_by = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True, related_name='deleted_logs', blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

