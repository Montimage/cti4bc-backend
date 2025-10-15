from django.contrib import admin
from .models import APIConfiguration, IPReputationRecord


@admin.register(APIConfiguration)
class APIConfigurationAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    fields = ('name', 'description', 'api_key', 'base_url', 'is_active')


@admin.register(IPReputationRecord)
class IPReputationRecordAdmin(admin.ModelAdmin):
    list_display = ('ip_address', 'is_malicious', 'threat_score', 'confidence_score', 'first_seen', 'last_checked')
    list_filter = ('is_malicious', 'first_seen', 'last_checked')
    search_fields = ('ip_address',)
    readonly_fields = ('first_seen', 'last_updated', 'last_checked')
    
    def has_add_permission(self, request):
        # Records are automatically created by the service
        return False
