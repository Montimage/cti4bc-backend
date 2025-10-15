from django.db import models
from organizations.models import Organization

class Strategy(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    template = models.JSONField(blank=True, null=True)
    organizations = models.ManyToManyField(Organization, blank=True, related_name='strategies')

    def __str__(self):
        return self.name