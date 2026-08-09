from django.urls import path
from apps.automl import views

from apps.automl.advisor import api_model_advisor
from apps.automl.simulator import api_run_simulation
from apps.automl.monitoring import api_get_model_monitoring

urlpatterns = [
    path('api/train/', views.api_trigger_training, name='api_trigger_training'),
    path('api/leaderboard/<str:project_id>/', views.api_get_leaderboard, name='api_get_leaderboard'),
    path('api/predict/', views.api_run_predictions, name='api_run_predictions'),
    path('api/download/<str:model_id>/', views.api_download_model, name='api_download_model'),
    path('api/delete/<str:model_id>/', views.api_delete_model, name='api_delete_model'),
    path('api/model-advisor/<str:dataset_id>/', api_model_advisor, name='api_model_advisor'),
    path('api/simulate/', api_run_simulation, name='api_run_simulation'),
    path('api/monitoring/<str:model_id>/<str:dataset_id>/', api_get_model_monitoring, name='api_get_model_monitoring'),
    path('api/auto-retrain/toggle/', views.api_toggle_auto_retrain, name='api_toggle_auto_retrain'),
    path('api/auto-retrain/status/<str:project_id>/', views.api_get_auto_retrain_status, name='api_get_auto_retrain_status'),
    path('api/job/status/<str:job_id>/', views.api_get_job_status, name='api_get_job_status'),
]

