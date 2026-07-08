from django.db import models
from django.contrib.auth.models import User
from event.models import Event


class Report(models.Model):
    # Lifecycle of the asynchronous generation task
    STATUS_PENDING = 'pending'
    STATUS_GENERATING = 'generating'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_GENERATING, 'Generating'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
    ]

    title = models.CharField(max_length=255)
    prompt = models.TextField(help_text="User prompt for report generation")
    generated_content = models.TextField(blank=True, default="", help_text="AI-generated report content")
    events = models.ManyToManyField(Event, related_name='reports', help_text="Events analyzed in this report")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reports')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Generation lifecycle
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING,
        help_text="Lifecycle status of the async report generation"
    )
    error_message = models.TextField(null=True, blank=True, help_text="Error details when generation failed")

    # Generation metadata
    tokens_used = models.IntegerField(null=True, blank=True, help_text="Number of tokens used for generation")
    generation_time = models.FloatField(null=True, blank=True, help_text="Time taken for generation in seconds")
    llm_provider = models.CharField(max_length=50, null=True, blank=True, help_text="LLM provider used for generation (e.g., 'gemini', 'ollama')")
    llm_model = models.CharField(max_length=100, null=True, blank=True, help_text="LLM model used for generation (e.g., 'gemini-1.5-flash', 'llama3.1:8b')")

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.user.username}"

    @property
    def events_count(self):
        return self.events.count()


class LLMConfig(models.Model):
    """
    Singleton runtime configuration for the LLM provider used to generate reports.

    Stored in the database (instead of mutating os.environ / rewriting the .env file)
    so the configuration is consistent across all Gunicorn workers and the qcluster
    process, survives restarts, and has no hardcoded filesystem path.
    """
    provider = models.CharField(max_length=50, default='gemini', help_text="Active LLM provider: 'gemini' or 'ollama'")
    ollama_model = models.CharField(max_length=100, default='llama3.1:8b', help_text="Model used when provider is 'ollama'")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'LLM configuration'
        verbose_name_plural = 'LLM configuration'

    def __str__(self):
        return f"LLMConfig(provider={self.provider}, ollama_model={self.ollama_model})"

    def save(self, *args, **kwargs):
        # Enforce a single row (singleton pattern)
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        """Return the singleton config, seeding it from env/settings on first use."""
        import os
        from django.conf import settings
        obj = cls.objects.filter(pk=1).first()
        if obj is None:
            obj = cls.objects.create(
                pk=1,
                provider=(os.environ.get('LLM_PROVIDER') or getattr(settings, 'LLM_PROVIDER', 'gemini')),
                ollama_model=(os.environ.get('OLLAMA_MODEL') or getattr(settings, 'OLLAMA_MODEL', 'llama3.1:8b')),
            )
        return obj
