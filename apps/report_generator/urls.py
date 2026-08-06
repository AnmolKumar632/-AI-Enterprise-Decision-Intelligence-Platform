from django.urls import path
from apps.report_generator import views

urlpatterns = [
    path('api/generate/', views.api_generate_report, name='api_generate_report'),
    path('api/list/<str:project_id>/', views.api_list_reports, name='api_list_reports'),
    path('api/download/<str:report_id>/', views.api_download_report, name='api_download_report'),
]
