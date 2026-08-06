from django.urls import path
from apps.eda import views

urlpatterns = [
    # API Endpoints
    path('api/summary/<str:dataset_id>/', views.api_eda_summary, name='api_eda_summary'),
    path('api/correlation/<str:dataset_id>/', views.api_eda_correlation, name='api_eda_correlation'),
    path('api/chart/<str:dataset_id>/<str:column>/', views.api_eda_chart_data, name='api_eda_chart_data'),
]
