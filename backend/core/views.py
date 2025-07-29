# core/views.py (با قابلیت نمایش جزئیات سیگنال‌های خنثی)

import asyncio
import logging
from django.http import JsonResponse
import httpx
from asgiref.sync import sync_to_async

from .exchange_fetcher import ExchangeFetcher
from engines.master_orchestrator import MasterOrchestrator
from engines.signal_adapter import SignalAdapter
from .utils import convert_numpy_types
from engines.trade_manager import TradeManager

logger = logging.getLogger(__name__)

async def system_status_view(request):
    exchanges_to_check = [{'name': 'Kucoin', 'status_url': 'https://api.kucoin.com/api/v1/timestamp'}, {'name': 'MEXC', 'status_url': 'https://api.mexc.com/api/v3/time'}, {'name': 'OKX', 'status_url': 'https://www.okx.com/api/v5/system/time'}]
    async with httpx.AsyncClient(timeout=10) as client:
        tasks = {asyncio.create_task(client.get(ex['status_url'])): ex['name'] for ex in exchanges_to_check}
        results = []
        for task in asyncio.as_completed(tasks):
            name = tasks[task]
            try:
                res = await task
                latency = round(res.elapsed.total_seconds() * 1000, 1)
                status = 'online' if 200 <= res.status_code < 400 else 'offline'
                results.append({'name': name, 'status': status, 'ping': f"{latency}ms"})
            except Exception:
                results.append({'name': name, 'status': 'offline', 'ping': '---'})
    return JsonResponse(results, safe=False)

async def market_overview_view(request):
    response_data = {}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            cg_task = asyncio.create_task(client.get("https://api.coingecko.com/api/v3/global"))
            fng_task = asyncio.create_task(client.get("https://api.alternative.me/fng/?limit=1"))
            cg_res = await cg_task
            if cg_res.status_code == 200:
                data = cg_res.json().get('data', {})
                response_data.update({'market_cap': data.get('total_market_cap', {}).get('usd', 0), 'volume_24h': data.get('total_volume', {}).get('usd', 0), 'btc_dominance': data.get('market_cap_percentage', {}).get('btc', 0)})
            fng_res = await fng_task
            if fng_res.status_code == 200:
                data = fng_res.json().get('data', [])
                if data: response_data['fear_and_greed'] = f"{data[0].get('value', 'N/A')} ({data[0].get('value_classification', 'Unknown')})"
    except Exception as e:
        logger.error(f"Error in market_overview_view: {e}")
    return JsonResponse(response_data)

async def get_composite_signal_view(request):
    symbol = request.GET.get('symbol', 'BTC').upper()
    fetcher = ExchangeFetcher()
    try:
        orchestrator = MasterOrchestrator()
        all_tf_analysis = {}
        timeframes = ['5m', '15m', '1h', '4h']
        tasks = [fetcher.get_first_successful_klines(symbol, tf) for tf in timeframes]
        results = await asyncio.gather(*tasks)
        for i, result in enumerate(results):
            if result and result[0] is not None:
                df, source = result
                tf = timeframes[i]
                analysis = orchestrator.analyze_single_dataframe(df, tf, symbol)
                analysis['source'] = source
                all_tf_analysis[tf] = analysis
        if not all_tf_analysis:
            return JsonResponse({"status": "NO_DATA", "message": f"Could not fetch market data for {symbol}."})
        
        final_result = await orchestrator.get_multi_timeframe_signal(all_tf_analysis)
        adapter = SignalAdapter(analytics_output=final_result)
        final_signal_object = adapter.combine()

        if not final_signal_object or final_signal_object.get("signal_type") == "HOLD":
            # --- اصلاح شد: اضافه کردن جزئیات تحلیل به خروجی NEUTRAL ---
            return JsonResponse({
                "status": "NEUTRAL",
                "message": "Market is neutral. No actionable signal found.",
                "details": convert_numpy_types(final_result)
            })
        
        return JsonResponse({"status": "SUCCESS", "signal": convert_numpy_types(final_signal_object)})
    except Exception as e:
        logger.error(f"CRITICAL ERROR in get_composite_signal_view for {symbol}: {e}", exc_info=True)
        return JsonResponse({"status": "ERROR", "message": "An internal server error occurred."})
    finally:
        await fetcher.close()

@sync_to_async
def _get_open_trades_sync():
    trade_manager = TradeManager()
    return trade_manager.get_open_trades()

async def list_open_trades_view(request):
    try:
        open_trades = await _get_open_trades_sync()
        return JsonResponse(open_trades, safe=False)
    except Exception as e:
        logger.error(f"Error in list_open_trades_view: {e}")
        return JsonResponse({'error': str(e)}, status=500)
