from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Admin Interface
    path('admin/', admin.site.urls),
    
    # UI Dashboard & Workspace (Home)
    path('', include('apps.dashboard.urls')),
    
    # Authentication & User Management
    path('auth/', include('apps.authentication.urls')),
    
    # Dataset Management & API
    path('datasets/', include('apps.dataset_management.urls')),
    
    # Automated EDA & Data Analytics
    path('eda/', include('apps.eda.urls')),
    
    # AutoML Engine
    path('automl/', include('apps.automl.urls')),
    
    # Time Series Forecasting
    path('forecasting/', include('apps.forecasting.urls')),
    
    # Fraud & Anomaly Detection
    path('anomaly/', include('apps.fraud_detection.urls')),
    
    # Natural Language Analytics
    path('nlp/', include('apps.nlp_query_engine.urls')),
    
    # Executive Report Generator
    path('reports/', include('apps.report_generator.urls')),
    
    # Real-time Notifications
    path('notifications/', include('apps.notifications.urls')),
    
    # AI Engine (Explainability & Personas)
    path('ai/', include('apps.ai_engine.urls')),
    
    # Global Search API
    path('api/search/', include('utilities.search_urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
