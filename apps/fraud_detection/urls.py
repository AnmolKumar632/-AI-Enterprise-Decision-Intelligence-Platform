from django.urls import path
from apps.fraud_detection import views

urlpatterns = [
    path('api/detect/', views.api_run_anomaly_detection, name='api_run_anomaly_detection'),
    path('api/results/<str:project_id>/', views.api_get_anomaly_results, name='api_get_anomaly_results'),
]
