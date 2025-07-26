# trading_app/urls.py - نسخه کامل و آپدیت شده

from django.urls import path
from core import views

urlpatterns = [
    # API های قبلی
    path('api/status/', views.system_status_view, name='system-status'),
    path('api/market-overview/', views.market_overview_view, name='market-overview'),
    path('api/data/all/', views.all_data_view, name='all-data'),
    path('api/analyze/candlesticks/', views.candlestick_analysis_view, name='candlestick-analysis'),
    path('api/analyze/indicators/', views.indicator_analysis_view, name='indicator-analysis'),
    path('api/analyze/structure/', views.market_structure_view, name='market-structure-analysis'),
    path('api/analyze/trend/', views.trend_analysis_view, name='trend-analysis'),
    
    # === API جدید برای تحلیل نهنگ‌ها اضافه شد ===
    path('api/analyze/whales/', views.whale_analysis_view, name='whale-analysis'),
]
