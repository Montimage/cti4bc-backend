from rest_framework import serializers
from .models import Strategy

# Serializer for listing strategies with minimal information
class StrategyListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Strategy
        fields = ['id', 'name']

# Serializer for detailed information of a strategy
class StrategyDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Strategy
        fields = ['id', 'name', 'description', 'template']

# Serializer for creating a new strategy
class AddStrategySerializer(serializers.ModelSerializer):
    class Meta:
        model = Strategy
        fields = ['name', 'description', 'template']
    
    def validate_template(self, value):
        # Clean the template by removing keys with empty values
        cleaned_template = {k: v for k, v in value.items() if v != ""}
        return cleaned_template
    
    def create(self, validated_data):
        strategy = Strategy.objects.create(**validated_data)
        return strategy