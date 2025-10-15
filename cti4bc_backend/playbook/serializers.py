from rest_framework import serializers
from .models import Playbook

class PlaybookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Playbook
        fields = ['external_id', 'event', 'data', 'updated_at']
        read_only_fields = ['updated_at']