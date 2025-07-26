from django.urls import path
from core import views

urlpatterns = [
    path('api/status/', views.system_status_view, name='system-status'),
    path('api/market-overview/', views.market_overview_view, name='market-overview'),
    path('api/data/all/', views.all_data_view, name='all-data'),
    path('api/analyze/candlesticks/', views.candlestick_analysis_view, name='candlestick-analysis'),
path('api/analyze/indicators/', views.indicator_analysis_view, name='indicator-analysis'),
]
