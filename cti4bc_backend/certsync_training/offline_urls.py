from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView
from cti4bc_backend.user_views import UserInfoView
from .views import SsoView, ConsumerReadyView

urlpatterns = [
    path("api/certsync-training/sso/", SsoView.as_view()),
    path("api/certsync-training/consumer-ready/", ConsumerReadyView.as_view()),
    path("api/token/refresh/", TokenRefreshView.as_view()),
    path("api/users/info/", UserInfoView.as_view()),
    path("event/", include("event.urls")),
    path("organizations/", include("organizations.urls")),
    path("misp_servers/", include("misp_servers.urls")),
    path("event_files/", include("event_files.urls")),
]
