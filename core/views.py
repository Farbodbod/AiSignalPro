from django.http import JsonResponse, HttpResponse
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback
import os
from .exchange_fetcher import SafeRequest, fetch_all_tickers_concurrently, MultiExchangeFetcher

# ===================================================================
# ویو Market Overview (بهینه‌سازی شده برای سرعت)
# ===================================================================
def market_overview_view(request):
    response_data = {'market_cap': 'N/A', 'volume_24h': 'N/A', 'btc_dominance': 'N/A', 'fear_and_greed': 'N/A'}
    
    # فقط از CoinMarketCap به عنوان منبع اصلی و سریع استفاده می‌کنیم
    try:
        cmc_fetcher = MultiExchangeFetcher('coinmarketcap').get_fetcher()
        cmc_data = cmc_fetcher.fetch_global_metrics()
        market_cap = cmc_data['market_cap']
        volume_24h = cmc_data['volume_24h']
        btc_dominance = cmc_data['btc_dominance']
        
        response_data['market_cap'] = market_cap
        response_data['volume_24h'] = volume_24h
        response_data['btc_dominance'] = btc_dominance
    except Exception as e:
        print(f"CoinMarketCap Error: {e}")

    # شاخص ترس و طمع همچنان از منبع خود خوانده می‌شود
    try:
        fng_url = "https://api.alternative.me/fng/?limit=1"
        fng_data = SafeRequest.get(fng_url)
        if fng_data and 'data' in fng_data and fng_data['data']:
            value = fng_data['data'][0]['value']
            text = fng_data['data'][0]['value_classification']
            response_data['fear_and_greed'] = f"{value} ({text})"
    except Exception as e_fng:
        print(f"Could not fetch Fear & Greed index: {e_fng}")
        
    return JsonResponse(response_data)


# ===================================================================
# ویو all_data_view (بهینه‌سازی شده برای سرعت)
# ===================================================================
def all_data_view(request):
    try:
        # محدود کردن منابع به ۳ صرافی سریع
        target_sources = ['kucoin', 'bitfinex', 'mexc']
        
        symbol_map = {
            'BTC': {'kucoin': 'BTC-USDT', 'bitfinex': 'BTCUSD', 'mexc': 'BTCUSDT'},
            'ETH': {'kucoin': 'ETH-USDT', 'bitfinex': 'ETHUSD', 'mexc': 'ETHUSDT'},
            'XRP': {'kucoin': 'XRP-USDT', 'bitfinex': 'XRPUSD', 'mexc': 'XRPUSDT'},
            'SOL': {'kucoin': 'SOL-USDT', 'bitfinex': 'SOLUSD', 'mexc': 'SOLUSDT'},
            'DOGE': {'kucoin': 'DOGE-USDT', 'bitfinex': 'DOGEUSD', 'mexc': 'DOGEUSDT'},
        }
        
        all_ticker_data = fetch_all_tickers_concurrently(target_sources, symbol_map)
        return JsonResponse(all_ticker_data)
        
    except Exception as e:
        return JsonResponse({'error': str(e), 'traceback': traceback.format_exc()}, status=500)


# ===================================================================
# ویوهای دیگر (بدون تغییر)
# ===================================================================
def check_exchange_status(exchange_info):
    name = exchange_info['name']; url = exchange_info['status_url']
    try:
        start_time = time.time(); response = requests.head(url, timeout=5); end_time = time.time()
        if response.status_code == 200:
            ping = int((end_time - start_time) * 1000); return {'name': name, 'status': 'online', 'ping': f'{ping}ms'}
        else: return {'name': name, 'status': 'offline', 'ping': 'Error'}
    except requests.exceptions.RequestException: return {'name': name, 'status': 'offline', 'ping': '---'}

def system_status_view(request):
    exchanges_to_check = [{'name': 'Kucoin', 'status_url': 'https://api.kucoin.com/api/v1/timestamp'},{'name': 'Gate.io', 'status_url': 'https://api.gate.io/api/v4/spot/time'},{'name': 'MEXC', 'status_url': 'https://api.mexc.com/api/v3/time'},{'name': 'OKX', 'status_url': 'https://www.okx.com/api/v5/system/time'},{'name': 'Bitfinex', 'status_url': 'https://api-pub.bitfinex.com/v2/platform/status'},{'name': 'Coingecko', 'status_url': 'https://api.coingecko.com/api/v3/ping'}]
    results = [];
    with ThreadPoolExecutor(max_workers=len(exchanges_to_check)) as executor:
        futures = {executor.submit(check_exchange_status, ex): ex for ex in exchanges_to_check}
        for future in futures: results.append(future.result())
    return JsonResponse(results, safe=False)

def home_page_view(request): return HttpResponse("<h1>Django Server is Running!</h1>")
