from django.db import models
from django.contrib.auth.models import User
from event.models import Event


class Report(models.Model):
    title = models.CharField(max_length=255)
    prompt = models.TextField(help_text="User prompt for report generation")
    generated_content = models.TextField(help_text="AI-generated report content")
    events = models.ManyToManyField(Event, related_name='reports', help_text="Events analyzed in this report")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reports')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
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
