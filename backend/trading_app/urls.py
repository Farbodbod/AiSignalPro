# trading_app/urls.py

from django.urls import path
from core import views

urlpatterns = [
    # این آدرس‌ها اکنون به توابع async متصل می‌شوند که جنگو به خوبی از آن پشتیبانی می‌کند
    path('api/status/', views.system_status_view, name='system-status'),
    path('api/market-overview/', views.market_overview_view, name='market-overview'),
    path('api/get-composite-signal/', views.get_composite_signal_view, name='composite-signal'),
    path('api/trades/open/', views.list_open_trades_view, name='list-open-trades'),
]
