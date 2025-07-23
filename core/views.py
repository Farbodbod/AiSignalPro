from django.http import JsonResponse, HttpResponse
from .exchange_fetcher import fetch_all_coins_concurrently
import time
from concurrent.futures import ThreadPoolExecutor
import requests

# (ویوهای home_page_view و system_status_view بدون تغییر باقی می‌مانند)
def home_page_view(request):
    return HttpResponse("<h1>Django Server is Running!</h1>")

def system_status_view(request):
    # ... (کد قبلی) ...
    exchanges_to_check = [
        {'name': 'Kucoin', 'status_url': 'https://api.kucoin.com/api/v1/timestamp'},
        {'name': 'Gate.io', 'status_url': 'https://api.gate.io/api/v4/spot/time'},
    ]
    results = []
    with ThreadPoolExecutor(max_workers=len(exchanges_to_check)) as executor:
        futures = {executor.submit(check_exchange_status, ex): ex for ex in exchanges_to_check}
        for future in futures:
            results.append(future.result())
    return JsonResponse(results, safe=False)

def check_exchange_status(exchange_info):
    # ... (کد قبلی) ...
    name = exchange_info['name']; url = exchange_info['status_url']
    try:
        start_time = time.time()
        response = requests.head(url, timeout=5)
        end_time = time.time()
        if response.status_code == 200:
            ping = int((end_time - start_time) * 1000)
            return {'name': name, 'status': 'online', 'ping': f'{ping}ms'}
        else: return {'name': name, 'status': 'offline', 'ping': 'Error'}
    except requests.exceptions.RequestException: return {'name': name, 'status': 'offline', 'ping': '---'}

# ===================================================================
# ویو جدید و اصلی ما که داده‌های تمام ارزها را برمی‌گرداند
# ===================================================================
def all_data_view(request):
    try:
        target_sources = ['kucoin', 'gate.io']
        
        # نقشه کامل نمادها برای ارزهای مورد نظر
        symbol_map = {
            'BTC': {'kucoin': 'BTC-USDT', 'gate.io': 'BTC_USDT'},
            'ETH': {'kucoin': 'ETH-USDT', 'gate.io': 'ETH_USDT'},
            'XRP': {'kucoin': 'XRP-USDT', 'gate.io': 'XRP_USDT'},
            'SOL': {'kucoin': 'SOL-USDT', 'gate.io': 'SOL_USDT'},
            'DOGE': {'kucoin': 'DOGE-USDT', 'gate.io': 'DOGE_USDT'},
        }
        
        # فراخوانی تابع جدید
        all_data = fetch_all_coins_concurrently(target_sources, symbol_map, '1h')
        
        # تبدیل دیتافریم‌ها به فرمت JSON
        json_friendly_data = {}
        for coin, sources in all_data.items():
            json_friendly_data[coin] = {}
            for source, df in sources.items():
                df_reset = df.reset_index()
                df_reset['timestamp'] = df_reset['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
                json_friendly_data[coin][source] = df_reset.to_dict('records')

        return JsonResponse(json_friendly_data)
        
    except Exception as e:
        # برگرداندن خطای دقیق در صورت بروز مشکل
        import traceback
        return JsonResponse({'error': str(e), 'traceback': traceback.format_exc()}, status=500)
