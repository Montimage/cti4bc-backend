from rest_framework import serializers
from .models import Report
from event.models import Event


class ReportListSerializer(serializers.ModelSerializer):
    """Serializer for listing reports with minimal information"""
    events_count = serializers.ReadOnlyField()
    user_name = serializers.CharField(source='user.username', read_only=True)
    content = serializers.CharField(source='generated_content', read_only=True)
    
    class Meta:
        model = Report
        fields = ['id', 'title', 'content', 'events_count', 'user_name', 'created_at', 'updated_at',
                 'tokens_used', 'generation_time', 'llm_provider', 'llm_model']


class ReportDetailSerializer(serializers.ModelSerializer):
    """Serializer for detailed report view"""
    events_count = serializers.ReadOnlyField()
    user_name = serializers.CharField(source='user.username', read_only=True)
    events = serializers.SerializerMethodField()
    content = serializers.CharField(source='generated_content', read_only=True)
    
    class Meta:
        model = Report
        fields = ['id', 'title', 'prompt', 'generated_content', 'content', 'events', 'events_count', 
                 'user_name', 'created_at', 'updated_at', 'tokens_used', 'generation_time',
                 'llm_provider', 'llm_model']
    
    def get_events(self, obj):
        """Return comprehensive event information"""
        events_info = []
        for event in obj.events.all():
            event_info = {
                'id': event.id,
                'external_id': event.external_id,
                'shared': event.shared,
                'organization': event.organization.name if event.organization else 'Unknown',
                'arrival_time': event.arrival_time,
                'created_at': event.arrival_time  # alias for frontend compatibility
            }
            
            # Try to extract comprehensive information from event data JSON
            if event.data and isinstance(event.data, dict):
                # Extract title/info
                event_info['title'] = (
                    event.data.get('title') or 
                    event.data.get('info') or 
                    event.data.get('summary') or 
                    event.data.get('alert') or
                    f"Event {event.id}"
                )
                
                # Extract description
                event_info['description'] = (
                    event.data.get('description') or
                    event.data.get('details') or
                    event.data.get('message') or
                    'No description available'
                )
                
                # Extract network information
                event_info['source_ip'] = (
                    event.data.get('source_ip') or
                    event.data.get('src_ip') or
                    event.data.get('srcip') or
                    None
                )
                
                event_info['destination_ip'] = (
                    event.data.get('destination_ip') or
                    event.data.get('dest_ip') or
                    event.data.get('dstip') or
                    None
                )
                
                # Add other relevant fields
                if 'severity' in event.data:
                    event_info['severity'] = event.data['severity']
                if 'status' in event.data:
                    event_info['status'] = event.data['status']
                if 'category' in event.data:
                    event_info['category'] = event.data['category']
                if 'type' in event.data:
                    event_info['type'] = event.data['type']
                    
                # Include the full data for complete information
                event_info['data'] = event.data
            else:
                event_info['title'] = f"Event {event.id}"
                event_info['description'] = 'No description available'
            
            events_info.append(event_info)
        
        return events_info


class ReportCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new reports"""
    events = serializers.PrimaryKeyRelatedField(
        many=True, 
        queryset=Event.objects.all(),
        required=True
    )
    
    class Meta:
        model = Report
        fields = ['title', 'prompt', 'events']
    
    def validate_events(self, value):
        """Ensure at least one event is selected"""
        if not value:
            raise serializers.ValidationError("At least one event must be selected.")
        return value
    
    def create(self, validated_data):
        events = validated_data.pop('events')
        report = Report.objects.create(**validated_data)
        report.events.set(events)
        return report
