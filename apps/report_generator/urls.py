from django.urls import path
from apps.report_generator import views

urlpatterns = [
    path('api/generate/', views.api_generate_report, name='api_generate_report'),
    path('api/list/<str:project_id>/', views.api_list_reports, name='api_list_reports'),
    path('api/download/<str:report_id>/', views.api_download_report, name='api_download_report'),
    path('api/view/<str:report_id>/', views.api_view_report, name='api_view_report'),
    path('api/generate-datastudio/', views.api_generate_datastudio_report, name='api_generate_datastudio_report'),
    path('api/delete/<str:report_id>/', views.api_delete_report, name='api_delete_report'),
]
