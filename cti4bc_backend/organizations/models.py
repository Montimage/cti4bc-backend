from django.db import models
from django.contrib.auth.models import User

class Organization(models.Model):
    """
    Represents an organization within the system.
    Attributes:
        id (AutoField): The primary key for the organization.
        name (CharField): The name of the organization.
        description (TextField): A brief description of the organization.
        email (EmailField): The contact email for the organization.
        external_id (CharField): MISP identifier for the organization.
        prefix (CharField): A unique prefix associated with the organization. (In the format UCX, where X is a number)
        users (ManyToManyField): The users associated with the organization.
      
    """
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    email = models.EmailField(max_length=254, blank=True)
    external_id = models.CharField(max_length=100, null=False)
    prefix = models.CharField(max_length=10, unique=True, null=False)
    users = models.ManyToManyField(User, blank=True, related_name='organizations')

    def __str__(self):
        return self.name