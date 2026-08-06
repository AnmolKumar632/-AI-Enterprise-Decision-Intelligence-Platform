from django.urls import path
from apps.notifications import views

urlpatterns = [
    path('api/list/', views.api_list_notifications, name='api_list_notifications'),
    path('api/read/<str:notification_id>/', views.api_mark_as_read, name='api_mark_as_read'),
]
