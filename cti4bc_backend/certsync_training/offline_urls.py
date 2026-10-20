from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView
from cti4bc_backend.kafka_views import StartConsumerView, StopConsumerView
from cti4bc_backend.health_views import available_misp_servers, database_health, external_services_health, message_queue_health
from cti4bc_backend.user_views import UserInfoView
from .views import SsoView, ConsumerReadyView

urlpatterns = [
    path("api/certsync-training/sso/", SsoView.as_view()),
    path("api/certsync-training/consumer-ready/", ConsumerReadyView.as_view()),
    path("api/token/refresh/", TokenRefreshView.as_view()),
    path("api/users/info/", UserInfoView.as_view()),
    path("api/health/database/", database_health),
    path("api/health/message-queue/", message_queue_health),
    path("api/health/external-services/", external_services_health),
    path("api/health/available-misp-servers/", available_misp_servers),
    path("consumer/start/", StartConsumerView.as_view()),
    path("consumer/stop/", StopConsumerView.as_view()),
    path("event/", include("event.urls")),
    path("organizations/", include("organizations.urls")),
    path("misp_servers/", include("misp_servers.urls")),
    path("event_files/", include("event_files.urls")),
]
