from django.urls import path
from core import views

urlpatterns = [
    # API اصلی برای دریافت سیگنال جامع
    path('api/get-composite-signal/', views.get_composite_signal_view, name='composite-signal'),
    
    # API های جدید برای مدیریت معامله
    path('api/trades/execute/', views.execute_trade_view, name='execute-trade'),
    path('api/trades/open/', views.list_open_trades_view, name='list-open-trades'),
]
