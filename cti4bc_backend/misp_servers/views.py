from certsync_training.contract import training_org, event_organizations
from django.conf import settings
from django.shortcuts import render, get_object_or_404
from rest_framework import viewsets, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import MISPServer
from .serializers import MISPServerSerializer
from event.models import Event

class MISPServerViewSet(viewsets.ModelViewSet):
    """
    API endpoint to manage MISP servers.
    """
    serializer_class = MISPServerSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """
        Filter MISP servers accessible to the current user.
        A user can only see servers belonging to their organization.
        """
        user = self.request.user
        if training_org(user):
            return MISPServer.objects.filter(organizations=training_org(user), url__in=[settings.CERTSYNC_PLATFORM_MISP_URL, settings.CERTSYNC_PLATFORM_MISP_URL.rstrip("/") + "/"]).distinct()
        if user.is_superuser:
            return MISPServer.objects.all()
        return MISPServer.objects.filter(organizations__in=user.organizations.all()).distinct()
    
    @action(detail=False, methods=['get'], url_path='for-event/(?P<event_id>[^/.]+)')
    def for_event(self, request, event_id=None):
        """
        Returns only MISP servers corresponding to the organization of the specified event.
        
        An event can only be shared with MISP servers belonging to the same organization
        as the event itself.
        """
        user = request.user
        
        try:
            # Get the specified event
            event = Event.objects.get(id=event_id)
            
            # Check permissions
            if (not user.is_staff or training_org(user)) and not event_organizations(user).filter(id=event.organization.id).exists():
                return Response({"error": "You don't have access to this event"}, status=403)
            
            # Get MISP servers from the same organization as the event
            misp_servers = MISPServer.objects.filter(organizations=event.organization)
            if training_org(user):
                misp_servers = misp_servers.filter(pk__in=self.get_queryset())
            
            # Serialize the data and return the response
            serializer = self.get_serializer(misp_servers, many=True)
            return Response(serializer.data)
            
        except Event.DoesNotExist:
            return Response({"error": "Event not found"}, status=404)
