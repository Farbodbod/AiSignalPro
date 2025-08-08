import logging
from django.http import JsonResponse
from rest_framework.decorators import api_view
from core.exchange_fetcher import ExchangeFetcher
from engines.master_orchestrator import MasterOrchestrator
import asyncio
import json

logger = logging.getLogger(__name__)

def load_config():
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Could not load config.json: {e}")
        return {}

@api_view(['GET'])
def get_composite_signal_view(request):
    symbol = request.GET.get('symbol', 'BTC/USDT')
    timeframe = request.GET.get('timeframe', '1h')
    
    try:
        fetcher = ExchangeFetcher()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
        
        df_tuple = loop.run_until_complete(fetcher.get_first_successful_klines(symbol, timeframe, limit=300))

        if df_tuple is None or df_tuple[0] is None:
            return JsonResponse({"status": "NO_DATA", "message": f"Could not fetch market data for {symbol}."}, status=404)
        
        dataframe, source = df_tuple
        
        config = load_config()
        orchestrator = MasterOrchestrator(config=config)
        
        # ✨ ارتقای کلیدی: ارکستراتور همیشه یک پکیج کامل برمی‌گرداند
        final_package = orchestrator.run_full_pipeline(dataframe, symbol, timeframe)

        # ما فقط نتیجه را مستقیماً به کاربر نمایش می‌دهیم
        return JsonResponse(final_package, status=200)

    except Exception as e:
        logger.critical(f"CRITICAL ERROR in get_composite_signal_view for {symbol}: {e}", exc_info=True)
        return JsonResponse({"status": "ERROR", "message": "An internal server error occurred."}, status=500)
