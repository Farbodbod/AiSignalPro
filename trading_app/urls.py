from django.contrib import admin
from django.urls import path
from core.views import (
    system_status_view, 
    market_overview_view, 
    all_data_view,
    candlestick_analysis_view # ویو جدید اضافه شد
)

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API های قبلی
    path('api/status/', system_status_view),
    path('api/market-overview/', market_overview_view),
    path('api/data/all/', all_data_view),
    
    # API جدید برای تحلیل کندل
    path('api/analysis/candlestick/', candlestick_analysis_view),
]
