from django.contrib import admin
from django.urls import path
from core.views import system_status_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/status/', system_status_view, name='system-status'),
    path('', system_status_view),  # برای تست سریع
]
