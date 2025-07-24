from django.contrib import admin
from django.urls import path
# ویو جدید را وارد می‌کنیم
from core.views import home_page_view, all_data_view, system_status_view, market_overview_view

urlpatterns = [
    path('', home_page_view, name='home'),
    path('admin/', admin.site.urls),
    
    path('api/status/', system_status_view, name='system-status'),
    path('api/data/all/', all_data_view, name='all-data'),
    
    # آدرس API جدید برای نمای کلی بازار
    path('api/market-overview/', market_overview_view, name='market-overview'),
]
