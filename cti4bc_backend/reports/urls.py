from django.urls import path
from .views import (
    ReportListCreateView,
    ReportDetailView,
    RegenerateReportView,
    LLMManagementView,
    LLMModelsView,
    get_llm_status
)

urlpatterns = [
    # Report endpoints
    path('', ReportListCreateView.as_view(), name='report_list_create'),
    path('<int:pk>/', ReportDetailView.as_view(), name='report_detail'),
    path('<int:pk>/regenerate/', RegenerateReportView.as_view(), name='report_regenerate'),
    
    # LLM management endpoints
    path('llm/', LLMManagementView.as_view(), name='llm_management'),
    path('llm/models/', LLMModelsView.as_view(), name='llm_models'),
    path('llm/status/', get_llm_status, name='llm_status'),
]
