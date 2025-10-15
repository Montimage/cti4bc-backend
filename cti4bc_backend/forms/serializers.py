from rest_framework import serializers
from .models import Form, FormAnswer
from organizations.models import Organization


class FormSerializer(serializers.ModelSerializer):
    """
    Serializer for Form model
    """
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    organization_names = serializers.SerializerMethodField()
    
    class Meta:
        model = Form
        fields = [
            'id', 'title', 'description', 'fields', 'organizations', 'organization_names',
            'created_by', 'created_by_username', 'created_at', 'updated_at', 'is_active'
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']

    def get_organization_names(self, obj):
        """Get names of all organizations for this form"""
        return [org.name for org in obj.organizations.all()]

    def validate_fields(self, value):
        """
        Validate that fields is a proper JSON structure for form fields
        Expected format: [{"name": "field1", "type": "text", "label": "Field 1", "required": true}, ...]
        """
        
        if not isinstance(value, list):
            raise serializers.ValidationError("Fields must be a list of field definitions")
        
        required_keys = ['name', 'type', 'label']
        valid_types = ['text', 'email', 'number', 'textarea', 'select', 'radio', 'checkbox', 'date', 'datetime', 'time', 'file']
        
        for i, field in enumerate(value):
            if not isinstance(field, dict):
                raise serializers.ValidationError(f"Field {i} must be a dictionary")
            
            # Check required keys
            for key in required_keys:
                if key not in field:
                    raise serializers.ValidationError(f"Field {i} is missing required key: {key}")
            
            # Validate field type
            if field['type'] not in valid_types:
                raise serializers.ValidationError(f"Field {i} has invalid type: {field['type']}. Must be one of: {valid_types}")
            
            # For select/radio fields, options are required
            if field['type'] in ['select', 'radio'] and 'options' not in field:
                raise serializers.ValidationError(f"Field {i} of type '{field['type']}' requires 'options' array")
        
        return value


class FormAnswerSerializer(serializers.ModelSerializer):
    """
    Serializer for FormAnswer model
    """
    form_title = serializers.CharField(source='form.title', read_only=True)
    filled_by_username = serializers.CharField(source='filled_by.username', read_only=True)
    event_info = serializers.CharField(source='event.data.info', read_only=True)
    event_name = serializers.SerializerMethodField()
    formFields = serializers.SerializerMethodField()
    
    class Meta:
        model = FormAnswer
        fields = [
            'id', 'form', 'form_title', 'event', 'event_info', 'event_name', 'answers',
            'filled_by', 'filled_by_username', 'filled_at', 'ip_address', 'formFields'
        ]
        read_only_fields = ['filled_by', 'filled_at']

    def get_event_name(self, obj):
        """Get event name or return None"""
        if obj.event and hasattr(obj.event, 'data') and obj.event.data:
            return obj.event.data.get('info', f'Event #{obj.event.id}')
        return f'Event #{obj.event.id}' if obj.event else None

    def get_formFields(self, obj):
        """Get form fields definition for editing purposes"""
        if obj.form and obj.form.fields:
            return obj.form.fields
        return []

    def validate_answers(self, value):
        """
        Validate that answers match the form structure
        """
        if not isinstance(value, dict):
            raise serializers.ValidationError("Answers must be a dictionary")
        
        # Get the form to validate against
        form = self.instance.form if self.instance else None
        if not form and 'form' in self.initial_data:
            try:
                form = Form.objects.get(id=self.initial_data['form'])
            except Form.DoesNotExist:
                raise serializers.ValidationError("Invalid form ID")
        
        if form:
            # Validate answers match form fields
            form_fields = {field['name']: field for field in form.fields}
            
            # Check required fields are present
            for field_name, field_config in form_fields.items():
                if field_config.get('required', False) and field_name not in value:
                    raise serializers.ValidationError(f"Required field '{field_name}' is missing")
            
            # Check all provided answers have corresponding form fields
            for field_name in value.keys():
                if field_name not in form_fields:
                    raise serializers.ValidationError(f"Unknown field '{field_name}' not in form definition")
        
        return value


class FormListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for listing forms
    """
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    organization_names = serializers.SerializerMethodField()
    answer_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Form
        fields = [
            'id', 'title', 'description', 'fields', 'organization_names',
            'created_by_username', 'created_at', 'is_active', 'answer_count'
        ]
    
    def get_organization_names(self, obj):
        """Get names of all organizations for this form"""
        return [org.name for org in obj.organizations.all()]
    
    def get_answer_count(self, obj):
        return obj.answers.count()
