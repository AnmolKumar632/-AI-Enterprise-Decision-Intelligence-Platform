from django.urls import path
from apps.dataset_management import views

urlpatterns = [
    # API Endpoints
    path('api/upload/', views.api_upload_dataset, name='api_upload_dataset'),
    path('api/list/<str:project_id>/', views.api_list_datasets, name='api_list_datasets'),
    path('api/detail/<str:dataset_id>/', views.api_dataset_detail, name='api_dataset_detail'),
    path('api/detail/<str:dataset_id>/quality/', views.api_dataset_quality, name='api_dataset_quality'),
    path('api/detail/<str:dataset_id>/lineage/', views.api_dataset_lineage, name='api_dataset_lineage'),
    path('api/clean/<str:dataset_id>/', views.api_clean_dataset, name='api_clean_dataset'),
    path('api/delete/<str:dataset_id>/', views.api_delete_dataset, name='api_delete_dataset'),
]
