from django.urls import path
from apps.nlp_query_engine import views

from apps.nlp_query_engine.root_cause import api_run_root_cause

urlpatterns = [
    path('api/query/', views.api_run_nlp_query, name='api_run_nlp_query'),
    path('api/root-cause/', api_run_root_cause, name='api_run_root_cause'),
    path('api/conversations/list/<str:project_id>/', views.api_list_conversations, name='api_list_conversations'),
    path('api/conversations/create/', views.api_create_conversation, name='api_create_conversation'),
    path('api/conversations/rename/', views.api_rename_conversation, name='api_rename_conversation'),
    path('api/conversations/delete/<str:conversation_id>/', views.api_delete_conversation, name='api_delete_conversation'),
    path('api/conversations/messages/<str:conversation_id>/', views.api_get_messages, name='api_get_messages'),
]
