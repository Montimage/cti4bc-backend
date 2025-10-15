from rest_framework import serializers
from .models import EventAttachment

class EventAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventAttachment
        fields = ['id', 'event', 'file', 'uploaded_at', 'uploaded_by']
        read_only_fields = ['uploaded_at', 'uploaded_by']