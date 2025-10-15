from django.contrib import admin
from .models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'events_count', 'created_at', 'tokens_used']
    list_filter = ['created_at', 'user']
    search_fields = ['title', 'prompt', 'user__username']
    readonly_fields = ['created_at', 'updated_at', 'tokens_used', 'generation_time']
    filter_horizontal = ['events']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'user', 'events')
        }),
        ('Content', {
            'fields': ('prompt', 'generated_content')
        }),
        ('Metadata', {
            'fields': ('tokens_used', 'generation_time', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
