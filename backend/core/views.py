from django.http import JsonResponse
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import traceback

# حالا از کلاس اصلاح شده و قدرتمند خود استفاده می‌کنیم
from .exchange_fetcher import ExchangeFetcher

logger = logging.getLogger(__name__)

# --- این تابع بدون تغییر باقی می‌ماند ---
def system_status_view(request):
    exchanges_to_check = [
        {'name': 'Kucoin', 'status_url': 'https://api.kucoin.com/api/v1/timestamp'},
        {'name': 'Gate.io', 'status_url': 'https://api.gate.io/api/v4/spot/time'},
        {'name': 'MEXC', 'status_url': 'https://api.mexc.com/api/v3/time'},
        {'name': 'OKX', 'status_url': 'https://www.okx.com/api/v5/system/time'},
        {'name': 'Toobit', 'status_url': 'https://api.toobit.com/api/v1/ping'},
        {'name': 'XT.com', 'status_url': 'https://api.xt.com/v4/public/ping'},
        {'name': 'CoinGecko', 'status_url': 'https://api.coingecko.com/api/v3/ping'},
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

# --- منطق این تابع حالا بازنویسی شده است ---
def market_overview_view(request):
    response_data = {'market_cap': 0, 'volume_24h': 0, 'btc_dominance': 0, 'fear_and_greed': 'N/A'}
    try:
        # استفاده از CoinGecko به عنوان یک منبع عمومی و قابل اطمینان
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

# --- منطق این تابع نیز با کد جدید جایگزین شده است ---
def all_data_view(request):
    try:
        fetcher = ExchangeFetcher()
        sources = ['kucoin', 'mexc', 'gateio', 'okx'] # صرافی‌های مورد نظر
        
        # تعریف نام ارزها در هر صرافی
        symbol_map = {
            'BTC': {'kucoin': 'BTC-USDT', 'mexc': 'BTCUSDT', 'gateio': 'BTC_USDT', 'okx': 'BTC-USDT'},
            'ETH': {'kucoin': 'ETH-USDT', 'mexc': 'ETHUSDT', 'gateio': 'ETH_USDT', 'okx': 'ETH-USDT'},
            'XRP': {'kucoin': 'XRP-USDT', 'mexc': 'XRPUSDT', 'gateio': 'XRP_USDT', 'okx': 'XRP-USDT'},
            'SOL': {'kucoin': 'SOL-USDT', 'mexc': 'SOLUSDT', 'gateio': 'SOL_USDT', 'okx': 'SOL-USDT'},
            'DOGE': {'kucoin': 'DOGE-USDT', 'mexc': 'DOGEUSDT', 'gateio': 'DOGE_USDT', 'okx': 'DOGE-USDT'},
        }

        all_data = fetcher.fetch_all_tickers_concurrently(sources, symbol_map)
        
        # اولویت‌بندی داده‌ها: اول KuCoin، بعد MEXC و سپس بقیه
        prioritized_data = {}
        priority_order = ['kucoin', 'mexc', 'okx', 'gateio']
        for coin, ex_data in all_data.items():
            for source in priority_order:
                if source in ex_data:
                    prioritized_data[coin] = {**ex_data[source], 'source': source}
                    break # به محض پیدا کردن اولین منبع معتبر، سراغ ارز بعدی می‌رویم
        
        return JsonResponse(prioritized_data)
        
    except Exception as e:
        logger.error(f"Error in all_data_view: {e}\n{traceback.format_exc()}")
        return JsonResponse({'error': 'Internal server error'}, status=500)
