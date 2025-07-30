# trading_app/urls.py (با لینک تست جدید)

from django.urls import path
from core import views

urlpatterns = [
    path('api/status/', views.system_status_view, name='system-status'),
    path('api/market-overview/', views.market_overview_view, name='market-overview'),
    path('api/get-composite-signal/', views.get_composite_signal_view, name='composite-signal'),
    path('api/trades/open/', views.list_open_trades_view, name='list-open-trades'),
    path('api/price-ticker/', views.price_ticker_view, name='price-ticker'),
    
    # --- ✨ لینک جدید برای تست مستقیم ارکستراتور ---
    path('api/run-test/', views.run_orchestrator_test_view, name='orchestrator-test'),
]
