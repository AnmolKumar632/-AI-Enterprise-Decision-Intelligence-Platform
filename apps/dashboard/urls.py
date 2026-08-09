from django.urls import path
from apps.dashboard import views

urlpatterns = [
    path('', views.dashboard_index, name='dashboard_index'),
    path('api/project/create/', views.api_create_project, name='api_create_project'),
    path('api/project/list/', views.api_list_projects, name='api_list_projects'),
    path('api/project/delete/<str:project_id>/', views.api_delete_project, name='api_delete_project'),
    path('api/visualization/data/', views.api_get_visualization_data, name='api_get_visualization_data'),
    path('api/dashboard/widget/save/', views.api_save_dashboard_widget, name='api_save_dashboard_widget'),
    path('api/dashboard/widget/list/<str:project_id>/', views.api_get_workspace_dashboard, name='api_get_workspace_dashboard'),
    path('api/dashboard/widget/delete/', views.api_delete_dashboard_widget, name='api_delete_dashboard_widget'),
]

