from django.urls import path
from apps.ai_engine import views
from apps.ai_engine.personas import api_get_business_personas

urlpatterns = [
    path('api/explain/<str:model_id>/<str:dataset_id>/<str:row_index>/', views.api_get_explainability, name='api_get_explainability'),
    path('api/personas/<str:dataset_id>/', api_get_business_personas, name='api_get_business_personas'),
]
