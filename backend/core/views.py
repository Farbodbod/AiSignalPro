# core/views.py (نسخه کامل و نهایی async)

import asyncio
import logging
from django.http import JsonResponse
import httpx

from .exchange_fetcher import ExchangeFetcher
from engines.master_orchestrator import MasterOrchestrator
from engines.signal_adapter import SignalAdapter
from .utils import convert_numpy_types
from engines.trade_manager import TradeManager # برای list_open_trades_view

logger = logging.getLogger(__name__)

async def system_status_view(request):
    """(نسخه پیشرفته) وضعیت آنلاین بودن صرافی‌ها را به صورت موازی چک می‌کند."""
    exchanges_to_check = [
        {'name': 'Kucoin', 'status_url': 'https://api.kucoin.com/api/v1/timestamp'},
        {'name': 'MEXC', 'status_url': 'https://api.mexc.com/api/v3/time'},
        {'name': 'OKX', 'status_url': 'https://www.okx.com/api/v5/system/time'}
    ]
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
    """(نسخه پیشرفته) نمای کلی بازار را به صورت موازی از منابع خارجی دریافت می‌کند."""
    response_data = {}
    async with httpx.AsyncClient(timeout=10) as client:
        cg_task = asyncio.create_task(client.get("https://api.coingecko.com/api/v3/global"))
        fng_task = asyncio.create_task(client.get("https://api.alternative.me/fng/?limit=1"))
        
        cg_res = await cg_task
        if cg_res.status_code == 200:
            data = cg_res.json().get('data', {})
            response_data.update({
                'market_cap': data.get('total_market_cap', {}).get('usd', 0),
                'volume_24h': data.get('total_volume', {}).get('usd', 0),
                'btc_dominance': data.get('market_cap_percentage', {}).get('btc', 0)
            })
        
        fng_res = await fng_task
        if fng_res.status_code == 200:
            data = fng_res.json().get('data', [])
            if data:
                response_data['fear_and_greed'] = f"{data[0].get('value', 'N/A')} ({data[0].get('value_classification', 'Unknown')})"

    return JsonResponse(response_data)


async def get_composite_signal_view(request):
    symbol = request.GET.get('symbol', 'BTC').upper()
    fetcher = ExchangeFetcher()
    try:
        orchestrator = MasterOrchestrator()
        all_tf_analysis = {}
        timeframes = ['5m', '15m', '1h', '4h']
        tasks = {asyncio.create_task(fetcher.get_first_successful_klines(symbol, tf)): tf for tf in timeframes}
        for task in asyncio.as_completed(tasks):
            tf = tasks[task]
            result = await task
            if result and result[0] is not None:
                df, source = result
                analysis = orchestrator.analyze_single_dataframe(df, tf, symbol)
                analysis['source'] = source
                all_tf_analysis[tf] = analysis
        if not all_tf_analysis:
            return JsonResponse({"status": "NO_DATA", "message": f"Could not fetch market data for {symbol}."})
        final_result = orchestrator.get_multi_timeframe_signal(all_tf_analysis)
        adapter = SignalAdapter(analytics_output=final_result)
        final_signal_object = adapter.combine()
        if not final_signal_object or final_signal_object.get("signal_type") == "HOLD":
            return JsonResponse({"status": "NEUTRAL", "message": "Market is neutral. No actionable signal found."})
        return JsonResponse({"status": "SUCCESS", "signal": convert_numpy_types(final_signal_object)})
    except Exception as e:
        logger.error(f"CRITICAL ERROR in get_composite_signal_view for {symbol}: {e}", exc_info=True)
        return JsonResponse({"status": "ERROR", "message": "An internal server error occurred."})
    finally:
        await fetcher.close()
        
# این توابع چون با دیتابیس کار می‌کنند و عملیات شبکه سنگین ندارند، می‌توانند sync باقی بمانند
def list_open_trades_view(request):
    try:
        trade_manager = TradeManager()
        open_trades = trade_manager.get_open_trades()
        return JsonResponse(open_trades, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
