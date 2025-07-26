import time
import requests
import logging
import traceback
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.http import JsonResponse

# موتورهای تحلیلی
from .exchange_fetcher import ExchangeFetcher
from engines.candlestick_reader import CandlestickPatternDetector
from engines.indicator_analyzer import calculate_indicators
from engines.market_structure_analyzer import LegPivotAnalyzer
from engines.trend_analyzer import analyze_trend
from engines.whale_analyzer import WhaleAnalyzer
from engines.divergence_detector import detect_divergences
# === این خط برای موتور جدید اضافه شده است ===
from engines.risk_manager import advanced_risk_analysis


logger = logging.getLogger(__name__)

# لیست صرافی‌ها به ترتیب اولویت برای استفاده در تمام تحلیل‌ها
EXCHANGE_FALLBACK_LIST = ['kucoin', 'mexc', 'okx', 'gateio']


# ==========================================================
# توابع عمومی و وضعیت سیستم
# ==========================================================

def system_status_view(request):
    # ... (کد این بخش بدون تغییر است)
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
    # ... (کد این بخش بدون تغییر است)
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
    # ... (کد این بخش بدون تغییر است)
    response_data = {'market_cap': 0, 'volume_24h': 0, 'btc_dominance': 0, 'fear_and_greed': 'N/A'}
    try:
        coingecko_url = "https://api.coingecko.com/api/v3/global"
        cg_data = requests.get(coingecko_url, timeout=10).json()
        if cg_data and 'data' in cg_data:
            data = cg_data['data']
            response_data.update({
                'market_cap': data.get('total_market_cap', {}).get('usd', 0),
                'volume_24h': data.get('total_volume', {}).get('usd', 0),
                'btc_dominance': data.get('market_cap_percentage', {}).get('btc', 0)
            })
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
    # ... (کد این بخش بدون تغییر است)
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
# تابع کمکی برای دریافت داده با منطق فال‌بک
# ==========================================================

def _get_data_with_fallback(fetcher, symbol, interval, limit, min_length):
    for source in EXCHANGE_FALLBACK_LIST:
        logger.info(f"Attempting to fetch data from {source} for {symbol}...")
        kline_data = fetcher.get_klines(source=source, symbol=symbol, interval=interval, limit=limit)
        if kline_data and len(kline_data) >= min_length:
            logger.info(f"Successfully fetched {len(kline_data)} candles from {source}.")
            return pd.DataFrame(kline_data), source
    return None, None


# ==========================================================
# توابع تحلیل با منطق فال‌بک (Fallback) هوشمند
# ==========================================================

def candlestick_analysis_view(request):
    # ... (کد این بخش بدون تغییر است)
    symbol = request.GET.get('symbol', 'BTC-USDT').upper()
    interval = request.GET.get('interval', '1h').lower()
    try:
        fetcher = ExchangeFetcher()
        df, source = _get_data_with_fallback(fetcher, symbol, interval, limit=100, min_length=50)
        if df is None:
            return JsonResponse({'error': 'Not enough kline data from any supported exchange.'}, status=404)
        for col in ['open', 'high', 'low', 'close', 'volume']: df[col] = pd.to_numeric(df[col])
        detector = CandlestickPatternDetector(df)
        patterns = detector.apply_filters(min_score=1.2, min_volume_ratio=0.8)
        return JsonResponse({'source': source, 'patterns': patterns}, safe=False)
    except Exception as e:
        logger.error(f"Error in candlestick_analysis_view: {e}\n{traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)

def indicator_analysis_view(request):
    # ... (کد این بخش بدون تغییر است)
    symbol = request.GET.get('symbol', 'BTC-USDT').upper()
    interval = request.GET.get('interval', '1h').lower()
    try:
        fetcher = ExchangeFetcher()
        df, source = _get_data_with_fallback(fetcher, symbol, interval, limit=200, min_length=100)
        if df is None:
            return JsonResponse({'error': 'Not enough kline data from any supported exchange.'}, status=404)
        for col in ['open', 'high', 'low', 'close', 'volume']: df[col] = pd.to_numeric(df[col])
        df_with_indicators = calculate_indicators(df)
        latest_values = {'source': source}
        for col in df_with_indicators.columns:
            if col not in ['timestamp', 'open', 'high', 'low', 'close', 'volume']:
                if not df_with_indicators[col].dropna().empty:
                    last_valid_value = df_with_indicators[col].dropna().iloc[-1]
                    latest_values[col] = round(last_valid_value, 4) if isinstance(last_valid_value, (int, float)) else last_valid_value
        return JsonResponse(latest_values)
    except Exception as e:
        logger.error(f"Error in indicator_analysis_view: {e}\n{traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)

def market_structure_view(request):
    # ... (کد این بخش بدون تغییر است)
    symbol = request.GET.get('symbol', 'BTC-USDT').upper()
    interval = request.GET.get('interval', '4h').lower()
    try:
        fetcher = ExchangeFetcher()
        df, source = _get_data_with_fallback(fetcher, symbol, interval, limit=300, min_length=250)
        if df is None:
            return JsonResponse({'error': 'Not enough kline data from any supported exchange.'}, status=404)
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col])
        analyzer = LegPivotAnalyzer(df, sensitivity=7)
        result = analyzer.analyze()
        result['source'] = source
        return JsonResponse(result)
    except Exception as e:
        logger.error(f"Error in market_structure_view: {e}\n{traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)

def trend_analysis_view(request):
    # ... (کد این بخش بدون تغییر است)
    symbol = request.GET.get('symbol', 'BTC-USDT').upper()
    interval = request.GET.get('interval', '1h').lower()
    try:
        fetcher = ExchangeFetcher()
        df, source = _get_data_with_fallback(fetcher, symbol, interval, limit=300, min_length=200)
        if df is None:
            return JsonResponse({'error': f'Not enough kline data from any supported exchange for trend analysis.'}, status=404)
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col])
        analysis_result = analyze_trend(df, timeframe=interval, ml_model=None)
        analysis_result['source'] = source
        return JsonResponse(analysis_result)
    except Exception as e:
        logger.error(f"Error in trend_analysis_view: {e}\n{traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)

def whale_analysis_view(request):
    # ... (کد این بخش بدون تغییر است)
    symbol = request.GET.get('symbol', 'BTC-USDT').upper()
    interval = request.GET.get('interval', '1h').lower()
    try:
        fetcher = ExchangeFetcher()
        df, source = _get_data_with_fallback(fetcher, symbol, interval, limit=500, min_length=100)
        if df is None:
            return JsonResponse({'error': 'Not enough kline data from any supported exchange.'}, status=404)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        df.set_index('timestamp', inplace=True)
        for col in ['open', 'high', 'low', 'close', 'volume']: df[col] = pd.to_numeric(df[col])
        analyzer = WhaleAnalyzer(timeframes=[interval])
        analyzer.update_data(interval, df)
        analyzer.generate_signals()
        signals = analyzer.get_signals(interval)
        for s in signals:
            if isinstance(s.get('time'), pd.Timestamp):
                s['time'] = s['time'].isoformat()
        return JsonResponse({'source': source, 'signals': signals}, safe=False)
    except Exception as e:
        logger.error(f"Error in whale_analysis_view: {e}\n{traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)

def divergence_analysis_view(request):
    # ... (کد این بخش بدون تغییر است)
    symbol = request.GET.get('symbol', 'BTC-USDT').upper()
    interval = request.GET.get('interval', '1h').lower()
    try:
        fetcher = ExchangeFetcher()
        df, source = _get_data_with_fallback(fetcher, symbol, interval, limit=300, min_length=100)
        if df is None:
            return JsonResponse({'error': 'Not enough kline data from any supported exchange.'}, status=404)
        for col in ['open', 'high', 'low', 'close', 'volume']: df[col] = pd.to_numeric(df[col])
        divergence_results = detect_divergences(df, order=5)
        final_result = {'source': source, 'divergences': divergence_results}
        return JsonResponse(final_result, safe=False)
    except Exception as e:
        logger.error(f"Error in divergence_analysis_view: {e}\n{traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)

# === تابع جدید برای محاسبه ریسک ===
def risk_analysis_view(request):
    try:
        balance = float(request.GET.get('balance', '10000'))
        risk_pct = float(request.GET.get('risk_pct', '0.01'))
        entry = float(request.GET.get('entry'))
        stop = float(request.GET.get('stop'))
        leverage = float(request.GET.get('leverage', '1.0'))
        
        targets_str = request.GET.get('targets')
        if not targets_str:
            raise ValueError("Parameter 'targets' is required.")
        targets = [float(t) for t in targets_str.split(',')]

        win_rate_str = request.GET.get('win_rate')
        win_rate = float(win_rate_str) if win_rate_str else 0.5

        atr_str = request.GET.get('atr')
        atr = float(atr_str) if atr_str else None

        analysis_results = advanced_risk_analysis(
            balance=balance,
            entry=entry,
            stop=stop,
            targets=targets,
            risk_pct=risk_pct,
            leverage=leverage,
            win_rate=win_rate,
            atr=atr,
            ml_model=None,
            ml_features=None
        )
        return JsonResponse(analysis_results)

    except (ValueError, TypeError) as ve:
        return JsonResponse({'error': f'Invalid or missing parameter: {str(ve)}'}, status=400)
    except Exception as e:
        logger.error(f"Error in risk_analysis_view: {e}\n{traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)
