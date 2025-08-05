# core/views.py (نسخه نهایی و قطعی 2.3 - کامل و بدون خلاصه‌نویسی)

import asyncio
import logging
from django.http import JsonResponse
import httpx

# وارد کردن تمام ماژول‌های لازم
from .exchange_fetcher import ExchangeFetcher
from engines.master_orchestrator import MasterOrchestrator, EngineConfig
from engines.signal_adapter import SignalAdapter
from .utils import convert_numpy_types
from engines.trade_manager import TradeManager
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)

# ساخت یک نمونه Singleton از ارکستراتور برای استفاده در تمام درخواست‌ها
engine_config = EngineConfig()
orchestrator = MasterOrchestrator(config=engine_config)

async def get_composite_signal_view(request):
    """
    نقطه ورودی اصلی API که حالا تمام جزئیات را در هر حالتی نمایش می‌دهد.
    """
    symbol = request.GET.get('symbol', 'BTC').upper()
    fetcher = ExchangeFetcher()
    try:
        timeframes = ['5m', '15m', '1h', '4h']
        tasks = [fetcher.get_first_successful_klines(symbol, tf) for tf in timeframes]
        results = await asyncio.gather(*tasks)
        
        dataframes = {}
        for i, result in enumerate(results):
            if result and result[0] is not None:
                df, source = result
                dataframes[timeframes[i]] = df

        if not dataframes:
            return JsonResponse({"status": "NO_DATA", "message": f"Could not fetch reliable market data for {symbol}."})

        final_result = await orchestrator.get_final_signal(dataframes, symbol)
        
        adapter = SignalAdapter(analytics_output=final_result)
        final_signal_object = adapter.generate_final_signal()

        if not final_signal_object:
            status = "NEUTRAL"
            message = final_result.get("message", "Market is neutral.")
            
            rule_based_signal = final_result.get("final_signal", "HOLD")
            ai_signal = final_result.get("gemini_confirmation", {}).get("signal", "HOLD")
            if (rule_based_signal == "BUY" and ai_signal == "SELL") or \
               (rule_based_signal == "SELL" and ai_signal == "BUY"):
                status = "VETOED_BY_AI"
                message = "Signal found but vetoed by AI due to conflicting analysis."

            return JsonResponse({
                "status": status,
                "message": message,
                "winning_strategy_details": final_result.get("winning_strategy", {}),
                "full_analysis_details": convert_numpy_types(final_result.get("full_analysis_details", {}))
            })
        
        return JsonResponse({
            "status": "SUCCESS", 
            "signal": convert_numpy_types(final_signal_object),
            "full_analysis_details": convert_numpy_types(final_result.get("full_analysis_details", {}))
        })

    except Exception as e:
        logger.error(f"CRITICAL ERROR in get_composite_signal_view for {symbol}: {e}", exc_info=True)
        return JsonResponse({"status": "ERROR", "message": "An internal server error occurred."})
    finally:
        await fetcher.close()

async def system_status_view(request):
    """ وضعیت آنلاین بودن و پینگ صرافی‌ها را بررسی می‌کند. """
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
                res.raise_for_status()
                latency = round(res.elapsed.total_seconds() * 1000, 1)
                results.append({'name': name, 'status': 'online', 'ping': f"{latency}ms"})
            except Exception:
                results.append({'name': name, 'status': 'offline', 'ping': '---'})
    return JsonResponse(results, safe=False)

async def market_overview_view(request):
    """ خلاصه‌ای از وضعیت کلی بازار (مارکت کپ، دامیننس، شاخص ترس و طمع) را ارائه می‌دهد. """
    response_data = {}
    try:
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
    except Exception as e:
        logger.error(f"Error in market_overview_view: {e}")
    return JsonResponse(response_data)

@sync_to_async
def _get_open_trades_sync():
    """ تابع همزمان را به صورت غیرهمزمان برای استفاده در view اجرا می‌کند. """
    trade_manager = TradeManager()
    return trade_manager.get_open_trades()

async def list_open_trades_view(request):
    """ لیستی از تمام معاملات باز را از دیتابیس برمی‌گرداند. """
    try:
        open_trades = await _get_open_trades_sync()
        return JsonResponse(open_trades, safe=False)
    except Exception as e:
        logger.error(f"Error in list_open_trades_view: {e}")
        return JsonResponse({'error': str(e)}, status=500)

async def price_ticker_view(request):
    """ آخرین قیمت ارزهای اصلی را از صرافی‌ها دریافت می‌کند. """
    fetcher = ExchangeFetcher()
    symbols_to_fetch = ['BTC', 'ETH', 'XRP', 'SOL', 'DOGE']
    try:
        tasks = [fetcher.get_first_successful_ticker(sym) for sym in symbols_to_fetch]
        results = await asyncio.gather(*tasks)
        successful_results = [res for res in results if res is not None]
        return JsonResponse(successful_results, safe=False)
    except Exception as e:
        logger.error(f"Error in price_ticker_view: {e}", exc_info=True)
        return JsonResponse({"error": "Failed to fetch ticker data"}, status=500)
    finally:
        await fetcher.close()
