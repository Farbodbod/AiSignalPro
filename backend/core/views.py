# core/views.py (نسخه جدید هماهنگ با معماری ماژولار)

import logging
from django.http import JsonResponse
from rest_framework.decorators import api_view
from core.exchange_fetcher import ExchangeFetcher
from engines.master_orchestrator import MasterOrchestrator # <-- استفاده از ارکستریتور جدید
import asyncio

logger = logging.getLogger(__name__)

@api_view(['GET'])
def get_composite_signal_view(request):
    """
    یک نقطه پایانی API برای دریافت تحلیل جامع و سیگنال‌های معاملاتی.
    """
    symbol = request.GET.get('symbol', 'BTC/USDT')
    timeframe = request.GET.get('timeframe', '1h')
    
    try:
        # دریافت داده‌های جدید از صرافی
        fetcher = ExchangeFetcher()
        # اجرای تابع async در یک محیط sync (جنگو)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        df = loop.run_until_complete(fetcher.get_first_successful_klines(symbol, timeframe))
        loop.run_until_complete(fetcher.close())

        if df is None or df[0] is None:
            return JsonResponse({"status": "NO_DATA", "message": "Could not fetch market data."}, status=404)
        
        dataframe = df[0]
        
        # ساخت نمونه از ارکستریتور جدید و اجرای تحلیل
        orchestrator = MasterOrchestrator()
        signals = orchestrator.run_analysis_for_symbol(dataframe)

        if signals:
            # اگر سیگنالی پیدا شد، اولین سیگنال را برمی‌گردانیم
            return JsonResponse({"status": "SUCCESS", "signal": signals[0]}, status=200)
        else:
            # اگر هیچ استراتژی سیگنالی تولید نکرد
            return JsonResponse({"status": "NEUTRAL", "message": "Market conditions do not meet any strategy criteria."}, status=200)

    except Exception as e:
        logger.critical(f"CRITICAL ERROR in get_composite_signal_view for {symbol}: {e}", exc_info=True)
        return JsonResponse({"status": "ERROR", "message": "An internal server error occurred."}, status=500)

