from django.http import JsonResponse, HttpResponse
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback
import os
from .exchange_fetcher import SafeRequest, fetch_all_tickers_concurrently, MultiExchangeFetcher

# (ویوهای market_overview_view, system_status_view, home_page_view بدون تغییر)
def market_overview_view(request): #...
    response_data = {'market_cap': 0, 'volume_24h': 0, 'btc_dominance': 0, 'fear_and_greed': 'N/A'}
    try:
        cmc_fetcher = MultiExchangeFetcher('coinmarketcap').get_fetcher()
        cmc_data = cmc_fetcher.fetch_global_metrics()
        response_data.update(cmc_data)
    except Exception as e:
        print(f"CoinMarketCap Error: {e}")
    try:
        fng_url = "https://api.alternative.me/fng/?limit=1"
        fng_data = SafeRequest.get(fng_url)
        if fng_data and 'data' in fng_data and fng_data['data']:
            value, text = fng_data['data'][0]['value'], fng_data['data'][0]['value_classification']
            response_data['fear_and_greed'] = f"{value} ({text})"
    except Exception as e_fng:
        print(f"Could not fetch F&G index: {e_fng}")
    return JsonResponse(response_data)
def check_exchange_status(exchange_info): #...
    name, url = exchange_info['name'], exchange_info['status_url']
    try:
        start_time = time.time(); response = requests.head(url, timeout=5); end_time = time.time()
        if response.status_code == 200:
            ping = int((end_time - start_time) * 1000); return {'name': name, 'status': 'online', 'ping': f'{ping}ms'}
        else: return {'name': name, 'status': 'offline', 'ping': 'Error'}
    except requests.exceptions.RequestException: return {'name': name, 'status': 'offline', 'ping': '---'}
def system_status_view(request): #...
    exchanges_to_check = [{'name': 'Kucoin', 'status_url': 'https://api.kucoin.com/api/v1/timestamp'},{'name': 'Gate.io', 'status_url': 'https://api.gate.io/api/v4/spot/time'},{'name': 'MEXC', 'status_url': 'https://api.mexc.com/api/v3/time'},{'name': 'OKX', 'status_url': 'https://www.okx.com/api/v5/system/time'},{'name': 'Bitfinex', 'status_url': 'https://api-pub.bitfinex.com/v2/platform/status'},{'name': 'Coingecko', 'status_url': 'https://api.coingecko.com/api/v3/ping'}]
    results = [];
    with ThreadPoolExecutor(max_workers=len(exchanges_to_check)) as executor:
        futures = {executor.submit(check_exchange_status, ex): ex for ex in exchanges_to_check}
        for future in as_completed(futures): results.append(future.result())
    return JsonResponse(results, safe=False)
def home_page_view(request): return HttpResponse("<h1>Django Server is Running!</h1>")

# ===================================================================
# ویو all_data_view (بازنویسی شده برای انتخاب هوشمند قیمت)
# ===================================================================
def all_data_view(request):
    try:
        target_sources = ['kucoin', 'bitfinex', 'mexc', 'gate.io', 'okx']
        priority_source = 'kucoin' # اولویت اول ما برای قیمت
        
        symbol_map = {
            'BTC': {'kucoin': 'BTC-USDT', 'bitfinex': 'BTCUSD', 'mexc': 'BTCUSDT', 'gate.io': 'BTC_USDT', 'okx': 'BTC-USDT'},
            'ETH': {'kucoin': 'ETH-USDT', 'bitfinex': 'ETHUSD', 'mexc': 'ETHUSDT', 'gate.io': 'ETH_USDT', 'okx': 'ETH-USDT'},
            'XRP': {'kucoin': 'XRP-USDT', 'bitfinex': 'XRPUSD', 'mexc': 'XRPUSDT', 'gate.io': 'XRP_USDT', 'okx': 'XRP-USDT'},
            'SOL': {'kucoin': 'SOL-USDT', 'bitfinex': 'SOLUSD', 'mexc': 'SOLUSDT', 'gate.io': 'SOL_USDT', 'okx': 'SOL-USDT'},
            'DOGE': {'kucoin': 'DOGE-USDT', 'bitfinex': 'DOGEUSD', 'mexc': 'DOGEUSDT', 'gate.io': 'DOGE_USDT', 'okx': 'DOGE-USDT'},
        }
        
        all_ticker_data = fetch_all_tickers_concurrently(target_sources, symbol_map)
        
        # منطق جدید برای انتخاب بهترین قیمت
        final_prices = {}
        for coin, sources in all_ticker_data.items():
            if priority_source in sources:
                final_prices[coin] = {'price': sources[priority_source], 'source': priority_source}
            elif sources:
                # اگر منبع اصلی نبود، اولین منبع موجود را انتخاب کن
                first_available_source = list(sources.keys())[0]
                final_prices[coin] = {'price': sources[first_available_source], 'source': first_available_source}

        return JsonResponse(final_prices)
        
    except Exception as e:
        return JsonResponse({'error': str(e), 'traceback': traceback.format_exc()}, status=500)
