from django.contrib import admin
from django.urls import path
# ویو را مستقیماً از اپلیکیشن core وارد می‌کنیم
from core.views import system_status_view 

urlpatterns = [
    path('admin/', admin.site.urls),
    # آدرس کامل API را مستقیماً اینجا تعریف می‌کنیم
    path('api/status/', system_status_view, name='system-status'),
]
