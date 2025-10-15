from django.shortcuts import render
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Organization

class OrganizationListView(APIView):
    """
    API View to list all organizations
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Get all organizations (for form selection)
        """
        if request.user.is_staff:
            # Superusers can see all organizations
            organizations = Organization.objects.all()
        else:
            # Regular users can only see their organizations
            organizations = request.user.organizations.all()

        # Simple serialization
        data = [
            {
                'id': org.id,
                'name': org.name,
                'description': org.description,
                'prefix': org.prefix
            }
            for org in organizations
        ]
        
        return Response({'organizations': data}, status=status.HTTP_200_OK)
    
class OrganizationsSummaryView(APIView):
    """
    API view to list all organizations (id and name only)
    Accessible to authenticated users
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organizations = Organization.objects.only('id', 'name').order_by('name')
        data = [{'id': org.id, 'name': org.name} for org in organizations]
        return Response({'organizations': data}, status=status.HTTP_200_OK)