from django.urls import path
from . import views

urlpatterns = [
    path('', views.StrategyListView.as_view(), name='strategy_list'),
    path('<int:id>/', views.StrategyDetailView.as_view(), name='strategy_detail'),
    path('add/', views.AddStrategyView.as_view(), name='add_strategy'),
    path('delete/<int:id>/', views.DeleteStrategyView.as_view(), name='delete_strategy'),
]