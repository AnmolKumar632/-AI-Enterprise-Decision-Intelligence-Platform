from django.urls import path
from apps.forecasting import views

urlpatterns = [
    path('api/predict/', views.api_run_forecast, name='api_run_forecast'),
    path('api/results/<str:project_id>/', views.api_get_forecast_results, name='api_get_forecast_results'),
]
