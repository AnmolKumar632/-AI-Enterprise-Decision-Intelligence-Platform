from django.urls import path
from utilities.search import api_global_search

urlpatterns = [
    path('', api_global_search, name='api_global_search'),
]
