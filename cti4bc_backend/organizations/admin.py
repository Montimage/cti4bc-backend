from django.contrib import admin
from .models import Organization, Sector


@admin.register(Sector)
class SectorAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'annex')
    list_filter = ('annex',)
    search_fields = ('name', 'code')
    ordering = ('annex', 'name')


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'prefix', 'sector_list')
    search_fields = ('name', 'prefix')
    filter_horizontal = ('sectors', 'users')

    def sector_list(self, obj):
        return ', '.join(s.name for s in obj.sectors.all()) or '—'
    sector_list.short_description = 'Sectors'