from django.http import JsonResponse, HttpResponse
import requests
import time
from concurrent.futures import ThreadPoolExecutor
import traceback
import os

# وارد کردن توابع از فایل کناری
from .exchange_fetcher import fetch_all_coins_concurrently, SafeRequest

# ===================================================================
# ویو برای نمای کلی بازار
# ===================================================================
def market_overview_view(request):
    try:
        coingecko_url = "https://api.coingecko.com/api/v3/global"
        global_data = SafeRequest.get(coingecko_url)
        if not global_data or 'data' not in global_data:
            raise Exception('Failed to fetch data from CoinGecko')
        
        cg_data = global_data['data']
        market_cap = cg_data['total_market_cap']['usd']
        volume_24h = cg_data['total_volume']['usd']
        btc_dominance = cg_data['market_cap_percentage']['btc']

        fng_url = "https://api.alternative.me/fng/?limit=1"
        fng_data = SafeRequest.get(fng_url)
        if not fng_data or 'data' not in fng_data or not fng_data['data']:
            raise Exception('Failed to fetch Fear & Greed index')
            
        fear_and_greed_value = fng_data['data'][0]['value']
        fear_and_greed_text = fng_data['data'][0]['value_classification']

        response_data = {
            'market_cap': f"${market_cap:,.0f}",
            'volume_24h': f"${volume_24h:,.0f}",
            'btc_dominance': f"{btc_dominance:.1f}%",
            'fear_and_greed': f"{fear_and_greed_value} ({fear_and_greed_text})"
        }
        
        return JsonResponse(response_data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# ===================================================================
# ویو برای وضعیت سیستم
# ===================================================================
def check_exchange_status(exchange_info):
    name = exchange_info['name']
    url = exchange_info['status_url']
    try:
        start_time = time.time()
        response = requests.head(url, timeout=5)
        end_time = time.time()
        if response.status_code == 200:
            ping = int((end_time - start_time) * 1000)
            return {'name': name, 'status': 'online', 'ping': f'{ping}ms'}
        else:
            return {'name': name, 'status': 'offline', 'ping': 'Error'}
    except requests.exceptions.RequestException:
        return {'name': name, 'status': 'offline', 'ping': '---'}

def system_status_view(request):
    exchanges_to_check = [
        {'name': 'Kucoin', 'status_url': 'https://api.kucoin.com/api/v1/timestamp'},
        {'name': 'Gate.io', 'status_url': 'https://api.gate.io/api/v4/spot/time'},
        {'name': 'MEXC', 'status_url': 'https://api.mexc.com/api/v3/time'},
        {'name': 'OKX', 'status_url': 'https://www.okx.com/api/v5/system/time'},
        {'name': 'Bitfinex', 'status_url': 'https://api-pub.bitfinex.com/v2/platform/status'},
        {'name': 'Coingecko', 'status_url': 'https://api.coingecko.com/api/v3/ping'},
    ]
    results = []
    with ThreadPoolExecutor(max_workers=len(exchanges_to_check)) as executor:
        futures = {executor.submit(check_exchange_status, ex): ex for ex in exchanges_to_check}
        for future in futures:
            results.append(future.result())
    return JsonResponse(results, safe=False)

# ===================================================================
# ویو برای آدرس ریشه
# ===================================================================
def home_page_view(request):
    return HttpResponse("<h1>Django Server is Running!</h1>")

# ===================================================================
# ویو برای دریافت داده‌های تمام ارزها
# ===================================================================
def all_data_view(request):
    try:
        target_sources = ['coingecko', 'kucoin', 'gate.io', 'okx', 'bitfinex', 'mexc']
        
        symbol_map = {
            'BTC': {'coingecko': 'bitcoin', 'kucoin': 'BTC-USDT', 'gate.io': 'BTC_USDT', 'okx': 'BTC-USDT', 'bitfinex': 'BTCUSD', 'mexc': 'BTCUSDT'},
            'ETH': {'coingecko': 'ethereum', 'kucoin': 'ETH-USDT', 'gate.io': 'ETH_USDT', 'okx': 'ETH-USDT', 'bitfinex': 'ETHUSD', 'mexc': 'ETHUSDT'},
            'XRP': {'coingecko': 'ripple', 'kucoin': 'XRP-USDT', 'gate.io': 'XRP_USDT', 'okx': 'XRP-USDT', 'bitfinex': 'XRPUSD', 'mexc': 'XRPUSDT'},
            'SOL': {'coingecko': 'solana', 'kucoin': 'SOL-USDT', 'gate.io': 'SOL_USDT', 'okx': 'SOL-USDT', 'bitfinex': 'SOLUSD', 'mexc': 'SOLUSDT'},
            'DOGE': {'coingecko': 'dogecoin', 'kucoin': 'DOGE-USDT', 'gate.io': 'DOGE_USDT', 'okx': 'DOGE-USDT', 'bitfinex': 'DOGEUSD', 'mexc': 'DOGEUSDT'},
        }
        
        all_data = fetch_all_coins_concurrently(target_sources, symbol_map, '1h')
        
        json_friendly_data = {}
        for coin, sources in all_data.items():
            json_friendly_data[coin] = {}
            for source, df in sources.items():
                df_reset = df.reset_index()
                df_reset['timestamp'] = df_reset['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
                json_friendly_data[coin][source] = df_reset.to_dict('records')

        return JsonResponse(json_friendly_data)
        
    except Exception as e:
        return JsonResponse({'error': str(e), 'traceback': traceback.format_exc()}, status=500)
