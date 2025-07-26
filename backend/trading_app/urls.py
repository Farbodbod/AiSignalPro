from django.urls import path
from core import views

urlpatterns = [
    # API های عمومی
    path('api/status/', views.system_status_view, name='system-status'),
    path('api/market-overview/', views.market_overview_view, name='market-overview'),
    path('api/data/all/', views.all_data_view, name='all-data'),
    
    # API های تحلیلی
    path('api/analyze/candlesticks/', views.candlestick_analysis_view, name='candlestick-analysis'),
    path('api/analyze/indicators/', views.indicator_analysis_view, name='indicator-analysis'),
    path('api/analyze/structure/', views.market_structure_view, name='market-structure-analysis'),
    path('api/analyze/trend/', views.trend_analysis_view, name='trend-analysis'),
    path('api/analyze/whales/', views.whale_analysis_view, name='whale-analysis'),
    path('api/analyze/divergence/', views.divergence_analysis_view, name='divergence-analysis'),
    
    # API های محاسباتی و هوش مصنوعی
    path('api/calculate/risk/', views.risk_analysis_view, name='risk-analysis'),
    path('api/predict/ai/', views.ai_prediction_view, name='ai-prediction'),

    # API نهایی برای سیگنال جامع
    path('api/get-final-signal/', views.get_final_signal_view, name='final-signal'),
]
