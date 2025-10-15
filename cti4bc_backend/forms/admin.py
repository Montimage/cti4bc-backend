from django.contrib import admin
from .models import Form, FormAnswer


@admin.register(Form)
class FormAdmin(admin.ModelAdmin):
    list_display = ['title', 'get_organizations', 'created_by', 'created_at', 'is_active']
    list_filter = ['is_active', 'organizations', 'created_at']
    search_fields = ['title', 'description']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = ['organizations']  # Use horizontal widget for many-to-many
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'organizations', 'is_active')
        }),
        ('Form Structure', {
            'fields': ('fields',),
            'description': 'JSON structure defining the form fields'
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_organizations(self, obj):
        """Display organizations in list view"""
        return ", ".join([org.name for org in obj.organizations.all()])
    get_organizations.short_description = 'Organizations'
    
    def save_model(self, request, obj, form, change):
        if not change:  # If creating a new form
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(FormAnswer)
class FormAnswerAdmin(admin.ModelAdmin):
    list_display = ['form', 'event', 'filled_by', 'filled_at']
    list_filter = ['filled_at', 'form', 'event__organization']
    search_fields = ['form__title', 'event__data__info', 'filled_by__username']
    readonly_fields = ['filled_at', 'ip_address']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('form', 'event', 'filled_by')
        }),
        ('Answers', {
            'fields': ('answers',),
            'description': 'JSON structure containing the form responses'
        }),
        ('Metadata', {
            'fields': ('filled_at', 'ip_address'),
            'classes': ('collapse',)
        })
    )
