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
    sectors = models.ManyToManyField('Sector', blank=True, related_name='organizations')

    def __str__(self):
        return self.name


class Sector(models.Model):
    """
    NIS2 sector of activity. `annex` distinguishes the two directive categories:
    'essential' (Annex I / highly critical) and 'important' (Annex II / other critical).
    An organization may operate in several sectors.
    """
    ESSENTIAL = 'essential'
    IMPORTANT = 'important'
    ANNEX_CHOICES = [
        (ESSENTIAL, 'Essential (Annex I)'),
        (IMPORTANT, 'Important (Annex II)'),
    ]

    code = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=128)
    annex = models.CharField(max_length=16, choices=ANNEX_CHOICES, default=ESSENTIAL)

    class Meta:
        ordering = ['annex', 'name']

    def __str__(self):
        return self.name