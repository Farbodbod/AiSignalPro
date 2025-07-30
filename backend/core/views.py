import asyncio
import logging
import traceback
from django.http import JsonResponse
import httpx
from asgiref.sync import sync_to_async

# --- ایمپورت های جدید برای تست ---
import pandas as pd
import numpy as np
# ---------------------------------

from .exchange_fetcher import ExchangeFetcher
from engines.master_orchestrator import MasterOrchestrator
from engines.signal_adapter import SignalAdapter
from .utils import convert_numpy_types
from engines.trade_manager import TradeManager

logger = logging.getLogger(__name__)


# =================================================================
#  VIEW جدید برای تست مستقیم ارکستراتور
# =================================================================
def create_sample_dataframe_for_test(rows=200):
    """یک دیتافریم نمونه برای تست ایجاد می‌کند."""
    data = {
        'timestamp': pd.to_datetime(pd.date_range(start='2025-01-01', periods=rows, freq='H')),
        'open': np.cumsum(np.random.uniform(-100, 100, size=rows)) + 40000,
        'high': 0, 'low': 0, 'close': 0,
        'volume': np.random.uniform(10, 100, size=rows)
    }
    df = pd.DataFrame(data)
    df['high'] = df['open'] + np.random.uniform(0, 500, size=rows)
    df['low'] = df['open'] - np.random.uniform(0, 500, size=rows)
    df['close'] = df['open'] + np.random.uniform(-200, 200, size=rows)
    return df

async def run_orchestrator_test_view(request):
    """
    این view یک تست مستقیم روی MasterOrchestrator اجرا کرده و نتیجه فیلتر الگوها را نشان می‌دهد.
    """
    logger.info("Starting direct orchestrator test via API...")
    try:
        sample_df = create_sample_dataframe_for_test()
        orchestrator = MasterOrchestrator()
        analysis_result = orchestrator.analyze_single_dataframe(sample_df, '1h', 'BTC-TEST')
        patterns = analysis_result.get('patterns', [])
        
        is_fixed = len(patterns) < 5 
        
        return JsonResponse({
            "test_status": "SUCCESS",
            "is_code_updated": is_fixed,
            "message": "Filter is working correctly!" if is_fixed else "FILTER IS NOT WORKING! Old code is running.",
            "detected_patterns_count": len(patterns),
            "detected_patterns": patterns
        })
    except Exception as e:
        logger.error(f"Error during orchestrator test view: {e}", exc_info=True)
        return JsonResponse({"test_status": "FAILED", "error": str(e)}, status=500)

# =================================================================
#  تمام VIEW های اصلی شما
# =================================================================

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
                df, source = result; tf = timeframes[i]
                analysis = orchestrator.analyze_single_dataframe(df, tf, symbol)
                analysis['source'] = source; all_tf_analysis[tf] = analysis

        if not all_tf_analysis:
            return JsonResponse({"status": "NO_DATA", "message": f"Could not fetch market data for {symbol}."})

        final_result = await orchestrator.get_multi_timeframe_signal(all_tf_analysis)
        adapter = SignalAdapter(analytics_output=final_result)
        final_signal_object = adapter.generate_final_signal()

        if not final_signal_object:
            detailed_overview = final_result.get("details", {})
            for tf_analysis in detailed_overview.values():
                if isinstance(tf_analysis, dict):
                    tf_analysis.pop('dataframe', None)
            
            return JsonResponse({
                "status": "NEUTRAL",
                "message": "Market is neutral. No high-quality signal found.",
                "scores": {
                    "rule_based_signal": final_result.get("rule_based_signal", "HOLD"),
                    "buy_score": final_result.get("buy_score", 0),
                    "sell_score": final_result.get("sell_score", 0),
                    "ai_signal": final_result.get("gemini_confirmation", {}).get("signal", "N/A"),
                },
                "full_analysis_details": convert_numpy_types(detailed_overview)
            })

        return JsonResponse({"status": "SUCCESS", "signal": convert_numpy_types(final_signal_object)})

    except Exception as e:
        logger.error(f"CRITICAL ERROR in get_composite_signal_view for {symbol}: {e}", exc_info=True)
        return JsonResponse({"status": "ERROR", "message": "An internal server error occurred."})
    finally:
        await fetcher.close()

async def system_status_view(request):
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
    trade_manager = TradeManager()
    return trade_manager.get_open_trades()

async def list_open_trades_view(request):
    try:
        open_trades = await _get_open_trades_sync()
        return JsonResponse(open_trades, safe=False)
    except Exception as e:
        logger.error(f"Error in list_open_trades_view: {e}")
        return JsonResponse({'error': str(e)}, status=500)

async def price_ticker_view(request):
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
