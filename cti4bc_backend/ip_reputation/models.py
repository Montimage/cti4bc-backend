from django.db import models


class APIConfiguration(models.Model):
    """
    Model for storing API configurations for external threat intelligence services.
    """
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    api_key = models.CharField(max_length=500)
    base_url = models.CharField(max_length=500)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Invalidate cache when configuration is updated
        try:
            from .utils_config import invalidate_api_cache
            invalidate_api_cache()
        except ImportError:
            pass
    
    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        # Invalidate cache when configuration is deleted
        try:
            from .utils_config import invalidate_api_cache
            invalidate_api_cache()
        except ImportError:
            pass


class IPReputationRecord(models.Model):
    """
    Model for storing IP reputation data.
    """
    ip_address = models.GenericIPAddressField()
    is_malicious = models.BooleanField(null=True, default=None)
    threat_score = models.FloatField(default=0)  # 0-100
    confidence_score = models.FloatField(default=0)  # 0-100
    
    # Sources that reported this IP as malicious
    reported_by = models.JSONField(default=dict)
    
    # Additional data from various sources
    details = models.JSONField(default=dict)
    
    first_seen = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    last_checked = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['ip_address']),
            models.Index(fields=['is_malicious']),
        ]
        
    def __str__(self):
        return f"{self.ip_address} - {'Malicious' if self.is_malicious else 'Clean'}"
