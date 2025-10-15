from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MISPServerViewSet

router = DefaultRouter()
router.register(r'', MISPServerViewSet, basename='misp-server')

urlpatterns = [
    path('', include(router.urls)),
]