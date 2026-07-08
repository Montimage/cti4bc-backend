from django.contrib import admin
from .models import Report, LLMConfig


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'status', 'events_count', 'created_at', 'tokens_used']
    list_filter = ['status', 'created_at', 'user']
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
        ('Generation', {
            'fields': ('status', 'error_message', 'llm_provider', 'llm_model')
        }),
        ('Metadata', {
            'fields': ('tokens_used', 'generation_time', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(LLMConfig)
class LLMConfigAdmin(admin.ModelAdmin):
    list_display = ['provider', 'ollama_model', 'updated_at']
