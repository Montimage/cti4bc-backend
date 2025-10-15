from rest_framework import serializers
from .models import Event, Organization

class EventSerializer(serializers.ModelSerializer):
    organization_id = serializers.IntegerField(write_only=True)
    external_id = serializers.CharField(required=False, allow_blank=True)
    time_stamp = serializers.CharField()
    probe_id = serializers.IntegerField()
    property = serializers.IntegerField()
    type = serializers.CharField()
    verdict = serializers.CharField()
    description = serializers.CharField()

    class Meta:
        model = Event
        fields = [
            'external_id', 'organization_id', 'time_stamp', 'probe_id', 'property',
            'type', 'verdict', 'description'
        ]
    
    def create(self, validated_data):
        organization_id = validated_data.pop('organization_id')
        organization = Organization.objects.get(id=organization_id)

        # Prepare basic event_data structure from validated_data
        event_data = {
            'timestamp': validated_data['timestamp'],
            'probe_id': validated_data['probe_id'],
            'property': validated_data['property'],
            'type': validated_data['type'],
            'verdict': validated_data['verdict'],
            'description': validated_data['description']
        }
        return Event.objects.create(
            organization=organization,
            external_id=validated_data.get('external_id', ''),
            data=event_data,
            shared=False
        )

class AttributeDetailSerializer(serializers.Serializer):
    type = serializers.CharField()
    value = serializers.CharField()
    to_ids = serializers.BooleanField()
    comment = serializers.CharField(allow_blank=True)
    category = serializers.CharField()
    action = serializers.DictField(required=False)

class AttributeSerializer(serializers.Serializer):
    RISK4BC = AttributeDetailSerializer(many=True, required=False, default=[])
    SOAR4BC = AttributeDetailSerializer(many=True, required=False, default=[])
    AWARE4BC = AttributeDetailSerializer(many=True, required=False, default=[])

class PlaybookSerializer(serializers.Serializer):
    type = serializers.CharField()
    value = serializers.CharField()
    to_ids = serializers.BooleanField()
    comment = serializers.CharField(allow_blank=True)
    category = serializers.CharField()

class ArtifactSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    share = serializers.BooleanField()

class ShareEventSerializer(serializers.Serializer):
    date = serializers.DictField(required = True)
    info = serializers.CharField(required = True)
    org_id = serializers.IntegerField(required = True)
    orgc_id = serializers.IntegerField(required = True)
    analysis = serializers.CharField()
    Attribute = AttributeSerializer(required = False, default={})
    published = serializers.BooleanField(default=False)
    distribution = serializers.CharField()
    threat_level_id = serializers.CharField()
    disable_correlation = serializers.BooleanField(default=False)
    event_creator_email = serializers.EmailField()
    proposal_email_lock = serializers.BooleanField(default=False)
    locked = serializers.BooleanField(default=False)
    artifacts = ArtifactSerializer(many=True, required=False, default=[])