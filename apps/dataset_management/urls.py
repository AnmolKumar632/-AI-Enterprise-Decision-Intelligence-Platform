from django.urls import path
from apps.dataset_management import views

urlpatterns = [
    # API Endpoints
    path('api/upload/', views.api_upload_dataset, name='api_upload_dataset'),
    path('api/list/<str:project_id>/', views.api_list_datasets, name='api_list_datasets'),
    path('api/detail/<str:dataset_id>/', views.api_dataset_detail, name='api_dataset_detail'),
    path('api/clean/<str:dataset_id>/', views.api_clean_dataset, name='api_clean_dataset'),
]
