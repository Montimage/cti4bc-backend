from rest_framework import serializers
from .models import MISPServer
from organizations.models import Organization


class MISPServerSerializer(serializers.ModelSerializer):
    organization_names = serializers.SerializerMethodField()
    organizations = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Organization.objects.all()
    )
    
    class Meta:
        model = MISPServer
        fields = ['id', 'name', 'url', 'apikey', 'organizations', 'organization_names']
        extra_kwargs = {
            'apikey': {'write_only': True}  # Hide API key in responses
        }
    
    def get_organization_names(self, obj):
        return [org.name for org in obj.organizations.all()]