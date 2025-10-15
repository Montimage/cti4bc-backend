from django.db import models
from organizations.models import Organization
from django.urls import reverse


class MISPServer(models.Model):
    """
    Represents a MISP server configuration.
    
    Attributes:
        name (CharField): The name to identify this MISP server.
        url (URLField): The full URL of the MISP instance.
        apikey (CharField): API key for authentication with the MISP server.
        organization (ForeignKey): The organization that owns this MISP server configuration.
    """
    name = models.CharField(max_length=100)
    url = models.URLField(max_length=255)
    apikey = models.CharField(max_length=255)
    organizations = models.ManyToManyField(
        Organization, 
        related_name='misp_servers'
    )
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = 'MISP Server'
        verbose_name_plural = 'MISP Servers'
