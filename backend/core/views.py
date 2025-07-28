# core/views.py (نسخه نهایی و مقاوم)

import time
import requests
import logging
import traceback
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.http import JsonResponse
from .exchange_fetcher import ExchangeFetcher
from engines.master_orchestrator import MasterOrchestrator
from engines.signal_adapter import SignalAdapter
from engines.trade_manager import TradeManager

# --- تنظیمات اولیه ---
logger = logging.getLogger(__name__)

# --- توابع کمکی ---
def convert_numpy_types(obj):
    """انواع داده‌های NumPy را به انواع استاندارد پایتون تبدیل می‌کند تا برای JSON مناسب باشند."""
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {k: convert_numpy_types(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [convert_numpy_types(i) for i in obj]
    return obj

# --- API Endpoints ---
def system_status_view(request):
    """وضعیت آنلاین بودن و پینگ صرافی‌های مختلف را بررسی می‌کند."""
    exchanges_to_check = [
        {'name': 'Kucoin', 'status_url': 'https://api.kucoin.com/api/v1/timestamp'},
        {'name': 'Gate.io', 'status_url': 'https://api.gate.io/api/v4/spot/time'},
        {'name': 'MEXC', 'status_url': 'https://api.mexc.com/api/v3/time'},
        {'name': 'OKX', 'status_url': 'https://www.okx.com/api/v5/system/time'}
    ]
    results = []
    with ThreadPoolExecutor(max_workers=len(exchanges_to_check)) as executor:
        future_to_exchange = {executor.submit(requests.get, ex['status_url'], timeout=5): ex for ex in exchanges_to_check}
        for future in as_completed(future_to_exchange):
            exchange_info = future_to_exchange[future]
            name = exchange_info['name']
            try:
                res = future.result()
                latency = round(res.elapsed.total_seconds() * 1000, 1)
                status = 'online' if 200 <= res.status_code < 400 else 'offline'
                results.append({'name': name, 'status': status, 'ping': f"{latency}ms"})
            except Exception:
                results.append({'name': name, 'status': 'offline', 'ping': '---'})
    return JsonResponse(results, safe=False)

def market_overview_view(request):
    """یک نمای کلی از وضعیت بازار (مانند مارکت کپ و شاخص ترس و طمع) ارائه می‌دهد."""
    response_data = {'market_cap': 0, 'volume_24h': 0, 'btc_dominance': 0, 'fear_and_greed': 'N/A'}
    try:
        cg_data = requests.get("https://api.coingecko.com/api/v3/global", timeout=10).json()
        if cg_data and 'data' in cg_data:
            data = cg_data['data']
            response_data.update({
                'market_cap': data.get('total_market_cap', {}).get('usd', 0),
                'volume_24h': data.get('total_volume', {}).get('usd', 0),
                'btc_dominance': data.get('market_cap_percentage', {}).get('btc', 0)
            })
    except Exception as e:
        logger.warning(f"Could not fetch CoinGecko data: {e}")
    try:
        fng_data = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10).json()
        if fng_data and 'data' in fng_data and fng_data['data']:
            value = fng_data['data'][0].get('value', 'N/A')
            classification = fng_data['data'][0].get('value_classification', 'Unknown')
            response_data['fear_and_greed'] = f"{value} ({classification})"
    except Exception as e:
        logger.warning(f"Could not fetch Fear & Greed data: {e}")
    return JsonResponse(response_data)

def all_data_view(request):
    """قیمت لحظه‌ای چندین ارز دیجیتال را از صرافی‌های مختلف دریافت می‌کند."""
    try:
        fetcher = ExchangeFetcher()
        symbol_map = {
            'BTC': {'kucoin': 'BTC-USDT', 'mexc': 'BTCUSDT', 'okx': 'BTC-USDT'},
            'ETH': {'kucoin': 'ETH-USDT', 'mexc': 'ETHUSDT', 'okx': 'ETH-USDT'},
            'SOL': {'kucoin': 'SOL-USDT', 'mexc': 'SOLUSDT', 'okx': 'SOL-USDT'}
        }
        sources_to_fetch = ['kucoin', 'mexc', 'okx']
        all_data = fetcher.fetch_all_tickers_concurrently(sources_to_fetch, symbol_map)
        return JsonResponse(all_data)
    except Exception as e:
        logger.error(f"Error in all_data_view: {e}", exc_info=True)
        return JsonResponse({'error': 'Internal server error'}, status=500)

def get_composite_signal_view(request):
    """API اصلی که تمام تحلیل‌ها را اجرا کرده و یک سیگنال نهایی و کامل تولید می‌کند."""
    symbol = request.GET.get('symbol', 'BTC-USDT').upper()
    try:
        fetcher = ExchangeFetcher()
        orchestrator = MasterOrchestrator()
        all_tf_analysis = {}
        timeframes = ['5m', '15m', '1h', '4h']
        
        with ThreadPoolExecutor() as executor:
            future_to_tf = {executor.submit(fetcher.get_klines_robust, symbol, tf): tf for tf in timeframes}
            for future in as_completed(future_to_tf):
                tf = future_to_tf[future]
                result = future.result()
                if result:
                    df, source = result
                    analysis = orchestrator.analyze_single_dataframe(df, tf, symbol=symbol)
                    analysis['source'] = source
                    all_tf_analysis[tf] = analysis
        
        if not all_tf_analysis:
            return JsonResponse({
                "status": "NO_DATA",
                "message": f"Could not fetch enough market data for {symbol} to perform analysis."
            })
        
        final_result = orchestrator.get_multi_timeframe_signal(all_tf_analysis)
        adapter = SignalAdapter(analytics_output=final_result)
        final_signal_object = adapter.combine()

        if final_signal_object is None or final_signal_object.get("signal_type") == "HOLD":
             return JsonResponse({
                "status": "NEUTRAL",
                "message": "Market conditions are neutral. No strong buy/sell signal found.",
                "details": convert_numpy_types(final_result)
            })
        
        return JsonResponse({
            "status": "SUCCESS",
            "signal": convert_numpy_types(final_signal_object)
        })

    except Exception as e:
        logger.error(f"CRITICAL ERROR in get_composite_signal_view for {symbol}: {e}", exc_info=True)
        return JsonResponse({
            "status": "ERROR",
            "message": "An internal server error occurred during analysis. The team has been notified."
        })

def list_open_trades_view(request):
    """لیستی از تمام معاملات باز را از دیتابیس برمی‌گرداند."""
    try:
        trade_manager = TradeManager()
        open_trades = trade_manager.get_open_trades()
        return JsonResponse(open_trades, safe=False)
    except Exception as e:
        logger.error(f"Error in list_open_trades_view: {e}", exc_info=True)
        return JsonResponse({'error': 'Failed to retrieve open trades.'}, status=500)

