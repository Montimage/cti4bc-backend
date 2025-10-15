"""
URL configuration for cti4bc_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from .kafka_views import StartConsumerView, StopConsumerView
from .user_views import UserRegistrationView, UserInfoView, CustomTokenObtainPairView, UpdateProfileView, ChangePasswordView
from .kafka_views import StartConsumerView, StopConsumerView, EnvVariablesView, GetConsumerStatusView, GetKafkaMessagesView
from .health_views import database_health, api_server_health, external_services_health, message_queue_health, available_misp_servers

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    #path('api/users/register/', UserRegistrationView.as_view(), name='user_registration'), # Only used for demonstration purposes
    path('api/users/info/', UserInfoView.as_view(), name='user_info'),
    path('api/users/update-profile/', UpdateProfileView.as_view(), name='update_profile'),
    path('api/users/change-password/', ChangePasswordView.as_view(), name='change_password'),
    path('strategy/', include('strategies.urls')),
    path('anonattributes/', include('anonattributes.urls')),
    path('event/', include('event.urls')),
    path('playbook/', include('playbook.urls')),
    path('forms/', include('forms.urls')),
    path('reports/', include('reports.urls')),
    path('organizations/', include('organizations.urls')),
    path('consumer/start/', StartConsumerView.as_view(), name='start_consumer'),
    path('consumer/stop/', StopConsumerView.as_view(), name='stop_consumer'),
    path('consumer/status/', GetConsumerStatusView.as_view(), name='consumer_status'),
    path('consumer/messages/', GetKafkaMessagesView.as_view(), name='kafka_messages'),
    path('consumer/env/', EnvVariablesView.as_view(), name='env_variables'),
    path('event_files/', include('event_files.urls')),
    path('misp_servers/', include('misp_servers.urls')),
    path('ip_reputation/', include('ip_reputation.urls')),
    path('api/health/database/', database_health, name='database_health'),
    path('api/health/api-server/', api_server_health, name='api_server_health'),
    path('api/health/external-services/', external_services_health, name='external_services_health'),
    path('api/health/message-queue/', message_queue_health, name='message_queue_health'),
    path('api/health/available-misp-servers/', available_misp_servers, name='available_misp_servers'),
]

# Serve media files in development mode
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)