import time
import requests
import logging
import traceback
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.http import JsonResponse

# موتورهای تحلیلی
from .exchange_fetcher import ExchangeFetcher
from engines.master_orchestrator import MasterOrchestrator
from engines.signal_adapter import SignalAdapter
from engines.trade_manager import TradeManager
from engines.indicator_analyzer import calculate_indicators
from engines.trend_analyzer import analyze_trend

logger = logging.getLogger(__name__)

EXCHANGE_FALLBACK_LIST = ['kucoin', 'mexc', 'okx', 'gateio']

def convert_numpy_types(obj):
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: convert_numpy_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(i) for i in obj]
    return obj

def _get_data_with_fallback(fetcher, symbol, interval, limit, min_length):
    for source in EXCHANGE_FALLBACK_LIST:
        try:
            kline_data = fetcher.get_klines(source=source, symbol=symbol, interval=interval, limit=limit)
            if kline_data and len(kline_data) >= min_length:
                logging.info(f"Successfully fetched {len(kline_data)} candles from {source} for {symbol}.")
                return pd.DataFrame(kline_data), source
        except Exception as e:
            logging.warning(f"Could not fetch from {source} for {symbol}: {e}")
    return None, None

# ==========================================================
# توابع عمومی که داشبورد به آنها نیاز دارد
# ==========================================================

def system_status_view(request):
    exchanges_to_check = [
        {'name': 'Kucoin', 'status_url': 'https://api.kucoin.com/api/v1/timestamp'},
        {'name': 'Gate.io', 'status_url': 'https://api.gate.io/api/v4/spot/time'},
        {'name': 'MEXC', 'status_url': 'https://api.mexc.com/api/v3/time'},
        {'name': 'OKX', 'status_url': 'https://www.okx.com/api/v5/system/time'},
    ]
    results = []
    with ThreadPoolExecutor(max_workers=len(exchanges_to_check)) as executor:
        futures = [executor.submit(check_exchange_status, ex) for ex in exchanges_to_check]
        for future in as_completed(futures):
            results.append(future.result())
    return JsonResponse(results, safe=False)

def check_exchange_status(exchange_info):
    try:
        start = time.time()
        res = requests.head(exchange_info['status_url'], timeout=5)
        if res.status_code == 405: 
            res = requests.get(exchange_info['status_url'], timeout=5)
        latency = round((time.time() - start) * 1000, 1)
        if 200 <= res.status_code < 300:
            return {'name': exchange_info['name'], 'status': 'online', 'ping': f"{latency}ms"}
        else:
            return {'name': exchange_info['name'], 'status': 'offline', 'ping': f"Err {res.status_code}"}
    except Exception:
        return {'name': exchange_info['name'], 'status': 'offline', 'ping': '---'}

def market_overview_view(request):
    response_data = {'market_cap': 0, 'volume_24h': 0, 'btc_dominance': 0, 'fear_and_greed': 'N/A'}
    try:
        coingecko_url = "https://api.coingecko.com/api/v3/global"
        cg_data = requests.get(coingecko_url, timeout=10).json()
        if cg_data and 'data' in cg_data:
            data = cg_data['data']
            response_data.update({'market_cap': data.get('total_market_cap', {}).get('usd', 0),'volume_24h': data.get('total_volume', {}).get('usd', 0),'btc_dominance': data.get('market_cap_percentage', {}).get('btc', 0)})
    except Exception as e_cg:
        logger.error(f"[CoinGecko] fallback failed: {e_cg}")
    try:
        fng_url = "https://api.alternative.me/fng/?limit=1"
        fng_data = requests.get(fng_url, timeout=10).json()
        if fng_data and 'data' in fng_data and fng_data['data']:
            value = fng_data['data'][0].get('value', 'N/A')
            text = fng_data['data'][0].get('value_classification', 'Unknown')
            response_data['fear_and_greed'] = f"{value} ({text})"
    except Exception as e_fng:
        logger.warning(f"[FNG] fetch failed: {e_fng}")
    return JsonResponse(response_data)

def all_data_view(request):
    try:
        fetcher = ExchangeFetcher()
        sources = ['kucoin', 'mexc', 'gateio', 'okx']
        symbol_map = {
            'BTC': {'kucoin': 'BTC-USDT', 'mexc': 'BTCUSDT', 'gateio': 'BTC_USDT', 'okx': 'BTC-USDT'},
            'ETH': {'kucoin': 'ETH-USDT', 'mexc': 'ETHUSDT', 'gateio': 'ETH_USDT', 'okx': 'ETH-USDT'},
            'XRP': {'kucoin': 'XRP-USDT', 'mexc': 'XRPUSDT', 'gateio': 'XRP_USDT', 'okx': 'XRP-USDT'},
            'SOL': {'kucoin': 'SOL-USDT', 'mexc': 'SOLUSDT', 'gateio': 'SOL_USDT', 'okx': 'SOL-USDT'},
            'DOGE': {'kucoin': 'DOGE-USDT', 'mexc': 'DOGEUSDT', 'gateio': 'DOGE_USDT', 'okx': 'DOGE-USDT'},
        }
        all_data = fetcher.fetch_all_tickers_concurrently(sources, symbol_map)
        prioritized_data = {}
        priority_order = ['kucoin', 'mexc', 'okx', 'gateio']
        for coin, ex_data in all_data.items():
            for source in priority_order:
                if source in ex_data:
                    prioritized_data[coin] = {**ex_data[source], 'source': source}
                    break
        return JsonResponse(prioritized_data)
    except Exception as e:
        logger.error(f"Error in all_data_view: {e}\n{traceback.format_exc()}")
        return JsonResponse({'error': 'Internal server error'}, status=500)

# ==========================================================
# API های نهایی
# ==========================================================

def get_composite_signal_view(request):
    symbol = request.GET.get('symbol', 'BTC-USDT').upper()
    requested_tf = request.GET.get('timeframe') 
    strategy = request.GET.get('strategy', 'balanced')
    try:
        fetcher = ExchangeFetcher()
        orchestrator = MasterOrchestrator()
        
        all_tf_analysis = {}
        timeframes_to_analyze = [requested_tf] if requested_tf else ['5m', '15m', '1h', '4h', '1d']

        for tf in timeframes_to_analyze:
            limit = 300 if tf in ['1h', '4h', '1d'] else 100
            min_length = 200 if tf in ['1h', '4h', '1d'] else 50
            
            df, source = _get_data_with_fallback(fetcher, symbol, tf, limit=limit, min_length=min_length)
            if df is not None:
                analysis = orchestrator.analyze_single_dataframe(df, tf)
                analysis['source'] = source
                analysis['symbol'] = symbol
                analysis['interval'] = tf
                all_tf_analysis[tf] = analysis
        
        if not all_tf_analysis:
            return JsonResponse({'error': 'Could not fetch enough data for any requested timeframe.'}, status=404)

        if requested_tf and requested_tf in all_tf_analysis:
             final_result = all_tf_analysis[requested_tf]
        else:
            final_result = orchestrator.get_multi_timeframe_signal(all_tf_analysis)

        adapter = SignalAdapter(analytics_output=final_result, strategy=strategy)
        final_signal_object = adapter.combine()

        return JsonResponse(convert_numpy_types(final_signal_object), safe=False)
    except Exception as e:
        logger.error(f"Error in get_composite_signal_view: {e}\n{traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)

def execute_trade_view(request):
    # This view is complex and depends on a signal object. 
    # For now, it's a placeholder. We can build its logic later.
    return JsonResponse({"status": "Endpoint is under construction."})

def list_open_trades_view(request):
    """لیست تمام معاملات باز را نمایش می‌دهد."""
    try:
        trade_manager = TradeManager()
        open_trades = trade_manager.get_open_trades()
        return JsonResponse(open_trades, safe=False)
    except Exception as e:
        logger.error(f"Error in list_open_trades_view: {e}\n{traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)
