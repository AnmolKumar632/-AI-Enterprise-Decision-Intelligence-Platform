from django.urls import path
from apps.nlp_query_engine import views

urlpatterns = [
    path('api/query/', views.api_run_nlp_query, name='api_run_nlp_query'),
]
