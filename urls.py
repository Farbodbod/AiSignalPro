# core/urls.py

from django.urls import path
from .views import system_status_view

urlpatterns = [
    path('status/', system_status_view, name='system-status'),
]
