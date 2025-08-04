# core/views.py (نسخه نهایی 2.2 - با نمایش وتوی AI)

import asyncio
import logging
from django.http import JsonResponse
import httpx

# وارد کردن ماژول‌های لازم با معماری جدید
from .exchange_fetcher import ExchangeFetcher
from engines.master_orchestrator import MasterOrchestrator, EngineConfig
from engines.signal_adapter import SignalAdapter
from .utils import convert_numpy_types
from engines.trade_manager import TradeManager
from asgiref.sync import sync_to_async


logger = logging.getLogger(__name__)

# ساخت یک نمونه Singleton از ارکستراتور
engine_config = EngineConfig()
orchestrator = MasterOrchestrator(config=engine_config)


async def get_composite_signal_view(request):
    """
    نقطه ورودی اصلی API که حالا وتوی هوش مصنوعی را به وضوح نمایش می‌دهد.
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

        # --- ✨ بخش اصلاح شده و کلیدی برای نمایش وتو ---
        if not final_signal_object:
            # بررسی می‌کنیم که آیا دلیل عدم وجود سیگنال، وتوی هوش مصنوعی بوده است یا خیر
            rule_based_signal = final_result.get("final_signal", "HOLD")
            ai_signal = final_result.get("gemini_confirmation", {}).get("signal", "HOLD")
            
            is_vetoed = (rule_based_signal == "BUY" and ai_signal == "SELL") or \
                        (rule_based_signal == "SELL" and ai_signal == "BUY")

            if is_vetoed:
                # اگر وتو شده بود، یک پاسخ اختصاصی با تمام جزئیات برمی‌گردانیم
                return JsonResponse({
                    "status": "VETOED_BY_AI",
                    "message": "A high-quality signal was found but vetoed by the AI due to conflicting analysis.",
                    "system_signal_details": {
                        "signal": rule_based_signal,
                        "winning_strategy": final_result.get("winning_strategy", {})
                    },
                    "ai_veto_details": {
                        "signal": ai_signal,
                        "explanation_fa": final_result.get("gemini_confirmation", {}).get("explanation_fa")
                    },
                    "full_analysis_details": convert_numpy_types(final_result.get("full_analysis_details", {}))
                })
            else:
                # اگر دلیل دیگری داشت، پاسخ خنثی معمولی را برمی‌گردانیم
                return JsonResponse({
                    "status": "NEUTRAL",
                    "message": final_result.get("message", "Market is neutral. No high-quality signal found."),
                    "winning_strategy_details": final_result.get("winning_strategy", {}),
                    "full_analysis_details": convert_numpy_types(final_result.get("full_analysis_details", {}))
                })
        # --- پایان بخش اصلاح شده ---
        
        return JsonResponse({"status": "SUCCESS", "signal": convert_numpy_types(final_signal_object)})

    except Exception as e:
        logger.error(f"CRITICAL ERROR in get_composite_signal_view for {symbol}: {e}", exc_info=True)
        return JsonResponse({"status": "ERROR", "message": "An internal server error occurred."})
    finally:
        await fetcher.close()

# ... سایر View های شما بدون تغییر باقی می‌مانند ...
async def system_status_view(request):
    # ... کد کامل از پاسخ‌های قبلی ...
    exchanges_to_check = [{'name': 'Kucoin', 'status_url': 'https://api.kucoin.com/api/v1/timestamp'},{'name': 'MEXC', 'status_url': 'https://api.mexc.com/api/v3/time'},{'name': 'OKX', 'status_url': 'https://www.okx.com/api/v5/system/time'}]
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
    # ... کد کامل از پاسخ‌های قبلی ...
    response_data = {}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            cg_task = asyncio.create_task(client.get("https://api.coingecko.com/api/v3/global"))
            fng_task = asyncio.create_task(client.get("https://api.alternative.me/fng/?limit=1"))
            cg_res = await cg_task
            if cg_res.status_code == 200:
                data = cg_res.json().get('data', {})
                response_data.update({'market_cap': data.get('total_market_cap', {}).get('usd', 0),'volume_24h': data.get('total_volume', {}).get('usd', 0),'btc_dominance': data.get('market_cap_percentage', {}).get('btc', 0)})
            fng_res = await fng_task
            if fng_res.status_code == 200:
                data = fng_res.json().get('data', [])
                if data: response_data['fear_and_greed'] = f"{data[0].get('value', 'N/A')} ({data[0].get('value_classification', 'Unknown')})"
    except Exception as e:
        logger.error(f"Error in market_overview_view: {e}")
    return JsonResponse(response_data)

@sync_to_async
def _get_open_trades_sync():
    # ... کد کامل از پاسخ‌های قبلی ...
    trade_manager = TradeManager()
    return trade_manager.get_open_trades()

async def list_open_trades_view(request):
    # ... کد کامل از پاسخ‌های قبلی ...
    try:
        open_trades = await _get_open_trades_sync()
        return JsonResponse(open_trades, safe=False)
    except Exception as e:
        logger.error(f"Error in list_open_trades_view: {e}")
        return JsonResponse({'error': str(e)}, status=500)

async def price_ticker_view(request):
    # ... کد کامل از پاسخ‌های قبلی ...
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
