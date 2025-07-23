from django.contrib import admin
from django.urls import path
# ویو جدید را وارد می‌کنیم
from core.views import home_page_view, all_data_view, system_status_view

urlpatterns = [
    path('', home_page_view, name='home'),
    path('admin/', admin.site.urls),
    
    # آدرس API قدیمی برای تست
    path('api/status/', system_status_view, name='system-status'),
    
    # آدرس API جدید و قدرتمند ما
    path('api/data/all/', all_data_view, name='all-data'),
]
