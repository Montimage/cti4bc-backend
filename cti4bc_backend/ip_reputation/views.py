from django.shortcuts import render
from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
import asyncio

from .models import APIConfiguration, IPReputationRecord
from .serializers import APIConfigurationSerializer, IPReputationRecordSerializer
from .services import IPReputationService


class APIConfigurationViewSet(viewsets.ModelViewSet):
    """
    API endpoint to manage API configurations for external threat intelligence services
    """
    queryset = APIConfiguration.objects.all()
    serializer_class = APIConfigurationSerializer
    permission_classes = [permissions.IsAdminUser]  # Only admin users can manage API configurations
    

class IPReputationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint to view IP reputation records
    """
    queryset = IPReputationRecord.objects.all()
    serializer_class = IPReputationRecordSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = IPReputationRecord.objects.all().order_by('-last_checked')
        
        # Filter by IP address
        ip_address = self.request.query_params.get('ip', None)
        if ip_address:
            queryset = queryset.filter(ip_address=ip_address)
            
        # Filter by malicious status
        is_malicious = self.request.query_params.get('malicious', None)
        if is_malicious is not None:
            is_malicious_bool = is_malicious.lower() in ['true', '1', 'yes']
            queryset = queryset.filter(is_malicious=is_malicious_bool)
            
        return queryset


class CheckIPReputationView(APIView):
    """
    API endpoint to check IP reputation from external sources
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, ip=None):
        if not ip:
            return Response({"error": "No IP address provided"}, status=status.HTTP_400_BAD_REQUEST)
            
        service = IPReputationService()
        result = asyncio.run(service.check_ip_reputation(ip))
        
        if "error" in result:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
            
        return Response(result)


class BulkCheckIPReputationView(APIView):
    """
    API endpoint to check reputation for multiple IPs at once
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        ips = request.data.get('ips', [])
        
        if not ips:
            return Response({"error": "No IP addresses provided"}, status=status.HTTP_400_BAD_REQUEST)
            
        service = IPReputationService()
        results = {}
        
        for ip in ips:
            result = asyncio.run(service.check_ip_reputation(ip))
            results[ip] = result
            
        return Response(results)
