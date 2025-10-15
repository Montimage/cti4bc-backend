from django.urls import path
from .views import (
    FormListCreateView,
    FormDetailView,
    FormAnswerListCreateView,
    FormAnswerDetailView,
    EventFormsView,
    GoogleFormImportView,
    FormStatsView
)

urlpatterns = [
    # Form endpoints
    path('', FormListCreateView.as_view(), name='form_list_create'),
    path('<int:pk>/', FormDetailView.as_view(), name='form_detail'),
    
    # Form answer endpoints
    path('answers/', FormAnswerListCreateView.as_view(), name='form_answer_list_create'),
    path('answers/<int:pk>/', FormAnswerDetailView.as_view(), name='form_answer_detail'),
    
    # Form statistics endpoints
    path('stats/', FormStatsView.as_view(), name='form_stats_overview'),
    path('<int:form_id>/stats/', FormStatsView.as_view(), name='form_stats_detail'),
    
    # Google Forms import endpoint (NEW: supports URL via Apps Script + JSON upload)
    path('import-google-form/', GoogleFormImportView.as_view(), name='google_form_import'),
    
    # Event-specific form endpoints
    path('event/<int:event_id>/forms/', EventFormsView.as_view(), name='event_forms'),
]
