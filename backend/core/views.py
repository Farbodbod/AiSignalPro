# core/views.py (نسخه نهایی هماهنگ با MasterOrchestrator v17+)

import logging
from django.http import JsonResponse
from rest_framework.decorators import api_view
from core.exchange_fetcher import ExchangeFetcher
from engines.master_orchestrator import MasterOrchestrator
import asyncio

logger = logging.getLogger(__name__)

@api_view(['GET'])
def get_composite_signal_view(request):
    """
    نقطه پایانی API برای دریافت تحلیل جامع و سیگنال‌های معاملاتی.
    """
    symbol = request.GET.get('symbol', 'BTC/USDT')
    timeframe = request.GET.get('timeframe', '1h')
    
    try:
        fetcher = ExchangeFetcher()
        # اجرای توابع async در یک محیط sync (جنگو)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # ما به ۲۰۰ کندل برای تحلیل کامل نیاز داریم
        df_tuple = loop.run_until_complete(fetcher.get_first_successful_klines(symbol, timeframe, limit=200))

        if df_tuple is None or df_tuple[0] is None:
            return JsonResponse({"status": "NO_DATA", "message": f"Could not fetch market data for {symbol}."}, status=404)
        
        dataframe, source = df_tuple
        
        orchestrator = MasterOrchestrator()
        
        # --- ✨ اصلاحیه کلیدی: استفاده از نام متد جدید و پاس دادن پارامترهای کامل ---
        final_signal_package = orchestrator.run_full_pipeline(dataframe, symbol, timeframe)

        if final_signal_package:
            # اگر سیگنالی پیدا شد، کل پکیج را برمی‌گردانیم
            return JsonResponse({"status": "SUCCESS", "signal_package": final_signal_package}, status=200)
        else:
            return JsonResponse({"status": "NEUTRAL", "message": "Market conditions do not meet any strategy criteria."}, status=200)

    except Exception as e:
        logger.critical(f"CRITICAL ERROR in get_composite_signal_view for {symbol}: {e}", exc_info=True)
        return JsonResponse({"status": "ERROR", "message": "An internal server error occurred."}, status=500)

