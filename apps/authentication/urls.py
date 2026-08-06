from django.urls import path
from apps.authentication import views

urlpatterns = [
    # UI Auth Pages
    path('login-page/', views.login_page, name='auth_login_page'),
    path('register-page/', views.register_page, name='auth_register_page'),
    
    # API Endpoints
    path('api/register/', views.api_register, name='api_register'),
    path('api/login/', views.api_login, name='api_login'),
    path('api/logout/', views.api_logout, name='api_logout'),
    path('api/verify/<str:token>/', views.api_verify_email, name='api_verify_email'),
    path('api/profile/', views.api_profile, name='api_profile'),
    path('api/audit-logs/', views.api_audit_logs, name='api_audit_logs'),
]
