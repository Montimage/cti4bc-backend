from django.urls import path
from . import views

urlpatterns = [
    path('<int:id>/', views.GetEventById.as_view(), name='get_by_id'),
    path('', views.GetEventsView.as_view(), name='get_all'),
    path('share/<int:id>/', views.ShareEventView.as_view(), name='share_event'),
    path('share-logs/', views.GetEventShareLogsView.as_view(), name='share_logs'),
    path('remote_incident/', views.RemoteIncidentView.as_view(), name='remote_incident'),
    path('update-share-status/<int:id>/', views.UpdateEventShareStatusView.as_view(), name='update_share_status'),
    path('update_risk_profile/<int:id>/', views.UpdateRiskProfileView.as_view(), name='update_risk_profile'),
    path('update_playbook/<int:id>/', views.UpdatePlaybookView.as_view(), name='update_playbook'),
]