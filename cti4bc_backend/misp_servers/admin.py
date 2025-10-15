from django.contrib import admin
from .models import MISPServer

@admin.register(MISPServer)
class MISPServerAdmin(admin.ModelAdmin):
    list_display = ('name', 'url', 'get_organizations')
    list_filter = ('organizations',)
    search_fields = ('name', 'url')

    def get_organizations(self, obj):
        return ", ".join([org.name for org in obj.organizations.all()])
    get_organizations.short_description = 'Organizations'
