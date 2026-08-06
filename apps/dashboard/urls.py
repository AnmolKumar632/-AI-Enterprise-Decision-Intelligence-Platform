from django.urls import path
from apps.dashboard import views

urlpatterns = [
    path('', views.dashboard_index, name='dashboard_index'),
    path('api/project/create/', views.api_create_project, name='api_create_project'),
    path('api/project/list/', views.api_list_projects, name='api_list_projects'),
]
