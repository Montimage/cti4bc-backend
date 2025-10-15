from django.urls import path
from . import views

urlpatterns = [
    path('new/', views.PlaybokCreateUpdateView.as_view(), name='new'),
    path('by_event/', views.PlaybookByEventView.as_view(), name='get_by_event'),
]