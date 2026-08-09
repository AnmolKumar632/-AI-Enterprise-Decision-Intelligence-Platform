from django.urls import path
from apps.notifications import views

from apps.notifications.alert_engine import api_list_alerts, api_mark_alert_read, api_trigger_scan_alerts

urlpatterns = [
    path('api/list/', views.api_list_notifications, name='api_list_notifications'),
    path('api/read/<str:notification_id>/', views.api_mark_as_read, name='api_mark_as_read'),
    path('api/delete/<str:notification_id>/', views.api_delete_notification, name='api_delete_notification'),
    path('api/alerts/list/<str:project_id>/', api_list_alerts, name='api_list_alerts'),
    path('api/alerts/read/', api_mark_alert_read, name='api_mark_alert_read'),
    path('api/alerts/scan/', api_trigger_scan_alerts, name='api_trigger_scan_alerts'),
]
