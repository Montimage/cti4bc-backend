from django.contrib import admin
from .models import Event, EventShareLog

admin.site.register(Event)
admin.site.register(EventShareLog)