from django.urls import path
from apps.automl import views

urlpatterns = [
    path('api/train/', views.api_trigger_training, name='api_trigger_training'),
    path('api/leaderboard/<str:project_id>/', views.api_get_leaderboard, name='api_get_leaderboard'),
    path('api/predict/', views.api_run_predictions, name='api_run_predictions'),
    path('api/download/<str:model_id>/', views.api_download_model, name='api_download_model'),
]
