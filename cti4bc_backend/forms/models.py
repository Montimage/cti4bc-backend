from django.db import models
from django.contrib.auth import get_user_model
from organizations.models import Organization

class Form(models.Model):
    """
    Model to store form templates that can be used when sharing events.
    
    Attributes:
        title (CharField): The title/name of the form
        description (TextField): Optional description of the form's purpose
        fields (JSONField): JSON structure defining the form fields and their properties
        organizations (ManyToManyField): The organizations that can access this form
        created_by (ForeignKey): The user who created this form
        created_at (DateTimeField): When the form was created
        updated_at (DateTimeField): When the form was last modified
        is_active (BooleanField): Whether this form is currently active/available
    """
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    fields = models.JSONField(
        help_text="JSON structure defining form fields: [{name, type, label, required, options}, ...]"
    )
    organizations = models.ManyToManyField(Organization, related_name='forms', blank=True)
    created_by = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True, related_name='created_forms')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class FormAnswer(models.Model):
    """
    Model to store answers/responses to forms when events are shared.
    
    Attributes:
        form (ForeignKey): Reference to the form that was filled
        event (ForeignKey): Reference to the event this form was filled for
        answers (JSONField): JSON structure containing the form responses
        filled_by (ForeignKey): The user who filled out this form
        filled_at (DateTimeField): When the form was filled
        ip_address (GenericIPAddressField): IP address where form was filled (optional)
    """
    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name='answers')
    event = models.ForeignKey('event.Event', on_delete=models.CASCADE, related_name='form_answers')
    answers = models.JSONField(
        help_text="JSON structure containing the form responses: {field_name: value, ...}"
    )
    filled_by = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True, related_name='form_answers')
    filled_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-filled_at']
        # Ensure one answer per form per event per user
        unique_together = ['form', 'event', 'filled_by']

    def __str__(self):
        return f"{self.form.title} - {self.event.id} - {self.filled_by.username if self.filled_by else 'Anonymous'}"
