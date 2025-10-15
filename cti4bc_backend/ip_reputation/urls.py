from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import APIConfigurationViewSet, IPReputationViewSet, CheckIPReputationView, BulkCheckIPReputationView

router = DefaultRouter()
router.register(r'configs', APIConfigurationViewSet)
router.register(r'records', IPReputationViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('check/<str:ip>/', CheckIPReputationView.as_view(), name='check-ip'),
    path('check/bulk/', BulkCheckIPReputationView.as_view(), name='bulk-check-ip'),
]
