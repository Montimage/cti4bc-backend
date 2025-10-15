from rest_framework import serializers
from .models import IPReputationRecord, APIConfiguration


class APIConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = APIConfiguration
        fields = ['id', 'name', 'description', 'base_url', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']
        
    # Custom create method to handle the API key securely
    def create(self, validated_data):
        api_key = self.context.get('request').data.get('api_key')
        if api_key:
            validated_data['api_key'] = api_key
        return super().create(validated_data)
    
    # Custom update method to handle the API key securely
    def update(self, instance, validated_data):
        api_key = self.context.get('request').data.get('api_key')
        if api_key:
            validated_data['api_key'] = api_key
        return super().update(instance, validated_data)


class IPReputationRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = IPReputationRecord
        fields = ['ip_address', 'is_malicious', 'threat_score', 'confidence_score', 
                 'reported_by', 'details', 'first_seen', 'last_updated', 'last_checked']
        read_only_fields = fields  # All fields are read-only
