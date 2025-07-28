import time, requests, logging, traceback, pandas as pd, numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.http import JsonResponse
from .exchange_fetcher import ExchangeFetcher
from engines.master_orchestrator import MasterOrchestrator
from engines.signal_adapter import SignalAdapter
from engines.trade_manager import TradeManager

logger = logging.getLogger(__name__)
EXCHANGE_FALLBACK_LIST = ['kucoin', 'mexc', 'okx', 'gateio']

def convert_numpy_types(obj):
    if isinstance(obj, np.integer): return int(obj)
    if isinstance(obj, np.floating): return float(obj)
    if isinstance(obj, np.ndarray): return obj.tolist()
    if isinstance(obj, dict): return {k: convert_numpy_types(v) for k, v in obj.items()}
    if isinstance(obj, list): return [convert_numpy_types(i) for i in obj]
    return obj

def _get_data_with_fallback(fetcher, symbol, interval, limit, min_length):
    for source in EXCHANGE_FALLBACK_LIST:
        try:
            kline_data = fetcher.get_klines(source=source, symbol=symbol, interval=interval, limit=limit)
            if kline_data and len(kline_data) >= min_length:
                return pd.DataFrame(kline_data), source
        except Exception as e:
            logging.warning(f"Could not fetch from {source} for {symbol}: {e}")
    return None, None

def system_status_view(request):
    exchanges_to_check = [{'name': 'Kucoin', 'status_url': 'https://api.kucoin.com/api/v1/timestamp'},{'name': 'Gate.io', 'status_url': 'https://api.gate.io/api/v4/spot/time'},{'name': 'MEXC', 'status_url': 'https://api.mexc.com/api/v3/time'},{'name': 'OKX', 'status_url': 'https://www.okx.com/api/v5/system/time'}]
    results = []
    with ThreadPoolExecutor(max_workers=len(exchanges_to_check)) as executor:
        futures = [executor.submit(check_exchange_status, ex) for ex in exchanges_to_check]
        for future in as_completed(futures): results.append(future.result())
    return JsonResponse(results, safe=False)

def check_exchange_status(exchange_info):
    try:
        start = time.time()
        res = requests.head(exchange_info['status_url'], timeout=5)
        if res.status_code == 405: res = requests.get(exchange_info['status_url'], timeout=5)
        latency = round((time.time() - start) * 1000, 1)
        if 200 <= res.status_code < 300: return {'name': exchange_info['name'], 'status': 'online', 'ping': f"{latency}ms"}
        else: return {'name': exchange_info['name'], 'status': 'offline', 'ping': f"Err {res.status_code}"}
    except Exception: return {'name': exchange_info['name'], 'status': 'offline', 'ping': '---'}

def market_overview_view(request):
    response_data = {'market_cap': 0, 'volume_24h': 0, 'btc_dominance': 0, 'fear_and_greed': 'N/A'}
    try:
        cg_data = requests.get("https://api.coingecko.com/api/v3/global", timeout=10).json()
        if cg_data and 'data' in cg_data:
            data = cg_data['data']
            response_data.update({'market_cap': data.get('total_market_cap', {}).get('usd', 0),'volume_24h': data.get('total_volume', {}).get('usd', 0),'btc_dominance': data.get('market_cap_percentage', {}).get('btc', 0)})
    except Exception: pass
    try:
        fng_data = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10).json()
        if fng_data and 'data' in fng_data and fng_data['data']:
            response_data['fear_and_greed'] = f"{fng_data['data'][0].get('value', 'N/A')} ({fng_data['data'][0].get('value_classification', 'Unknown')})"
    except Exception: pass
    return JsonResponse(response_data)

def all_data_view(request):
    try:
        fetcher = ExchangeFetcher()
        symbol_map = {'BTC': {'kucoin': 'BTC-USDT', 'mexc': 'BTCUSDT'},'ETH': {'kucoin': 'ETH-USDT', 'mexc': 'ETHUSDT'},'SOL': {'kucoin': 'SOL-USDT', 'mexc': 'SOLUSDT'}}
        all_data = fetcher.fetch_all_tickers_concurrently(list(symbol_map.keys()), symbol_map)
        return JsonResponse(all_data)
    except Exception: return JsonResponse({'error': 'Internal server error'}, status=500)

def get_composite_signal_view(request):
    symbol = request.GET.get('symbol', 'BTC-USDT').upper()
    requested_tf = request.GET.get('timeframe') 
    try:
        fetcher = ExchangeFetcher()
        orchestrator = MasterOrchestrator()
        all_tf_analysis = {}
        timeframes = [requested_tf] if requested_tf else ['15m', '1h', '4h']
        for tf in timeframes:
            limit = 300 if tf in ['1h', '4h'] else 100
            min_length = 200 if tf in ['1h', '4h'] else 50
            df, source = _get_data_with_fallback(fetcher, symbol, tf, limit=limit, min_length=min_length)
            if df is not None:
                analysis = orchestrator.analyze_single_dataframe(df, tf, symbol)
                analysis['source'] = source
                all_tf_analysis[tf] = analysis
        if not all_tf_analysis: return JsonResponse({'error': 'Could not fetch enough data.'}, status=404)
        
        final_result = orchestrator.get_multi_timeframe_signal(all_tf_analysis)
        adapter = SignalAdapter(analytics_output=final_result)
        final_signal_object = adapter.combine()
        return JsonResponse(convert_numpy_types(final_signal_object), safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def list_open_trades_view(request):
    try:
        trade_manager = TradeManager()
        open_trades = trade_manager.get_open_trades()
        return JsonResponse(open_trades, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
