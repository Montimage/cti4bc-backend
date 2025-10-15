from django.urls import path
from .views import OrganizationListView
from .views import OrganizationsSummaryView

urlpatterns = [
    path('', OrganizationListView.as_view(), name='organization-list'),
    path('summary/', OrganizationsSummaryView.as_view(), name='organization-summary'),
]