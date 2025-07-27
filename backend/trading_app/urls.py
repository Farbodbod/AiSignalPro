# trading_app/urls.py (نسخه کامل و نهایی)

from django.urls import path
from core import views

urlpatterns = [
    # === API های عمومی و پایه که داشبورد نیاز دارد ===
    path('api/status/', views.system_status_view, name='system-status'),
    path('api/market-overview/', views.market_overview_view, name='market-overview'),
    path('api/data/all/', views.all_data_view, name='all-data'),
    
    # === API های مدیریت معامله ===
    path('api/trades/execute/', views.execute_trade_view, name='execute-trade'),
    path('api/trades/open/', views.list_open_trades_view, name='list-open-trades'),

    # === API نهایی و جامع برای سیگنال ===
    path('api/get-composite-signal/', views.get_composite_signal_view, name='composite-signal'),
]
