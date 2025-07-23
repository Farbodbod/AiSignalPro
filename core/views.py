from django.http import JsonResponse, HttpResponse
import requests
import time
from concurrent.futures import ThreadPoolExecutor

# وارد کردن موتور تحلیل داده از فایل کناری
from .exchange_fetcher import fetch_all_sources_concurrently

# ===================================================================
# ویو جدید و حرفه‌ای برای وضعیت سیستم
# ===================================================================

def check_exchange_status(exchange_info):
    """یک درخواست سبک به هر صرافی برای چک کردن وضعیت و پینگ ارسال می‌کند."""
    name = exchange_info['name']
    url = exchange_info['status_url']
    try:
        start_time = time.time()
        # ما فقط به هدرها نیاز داریم که سریع‌تر است
        response = requests.head(url, timeout=5)
        end_time = time.time()
        
        # اگر پاسخ موفقیت‌آمیز بود
        if response.status_code == 200:
            ping = int((end_time - start_time) * 1000)
            return {'name': name, 'status': 'online', 'ping': f'{ping}ms'}
        else:
            return {'name': name, 'status': 'offline', 'ping': 'Error'}
            
    except requests.exceptions.RequestException:
        return {'name': name, 'status': 'offline', 'ping': '---'}

def system_status_view(request):
    """وضعیت تمام صرافی‌ها را به صورت همزمان و موازی چک می‌کند."""
    exchanges_to_check = [
        {'name': 'Kucoin', 'status_url': 'https://api.kucoin.com/api/v1/timestamp'},
        {'name': 'Gate.io', 'status_url': 'https://api.gate.io/api/v4/spot/time'},
        {'name': 'MEXC', 'status_url': 'https://api.mexc.com/api/v3/time'},
        {'name': 'OKX', 'status_url': 'https://www.okx.com/api/v5/system/time'},
        {'name': 'Bitfinex', 'status_url': 'https://api-pub.bitfinex.com/v2/platform/status'},
        {'name': 'Coingecko', 'status_url': 'https://api.coingecko.com/api/v3/ping'},
        {'name': 'Telegram', 'status_url': 'https://api.telegram.org'}
    ]
    
    results = []
    # استفاده از تردها برای ارسال همزمان تمام درخواست‌ها
    with ThreadPoolExecutor(max_workers=len(exchanges_to_check)) as executor:
        # ارسال وظایف به ترد پول
        futures = {executor.submit(check_exchange_status, ex): ex for ex in exchanges_to_check}
        # جمع‌آوری نتایج
        for future in futures:
            results.append(future.result())
            
    return JsonResponse(results, safe=False)


# ===================================================================
# ویوهای دیگر (بدون تغییر)
# ===================================================================

def home_page_view(request):
    return HttpResponse("<h1>Django Server is Running!</h1>")

def all_data_view(request):
    """ویو دریافت همزمان دیتای کندل از چند صرافی"""
    try:
        target_sources = ['kucoin', 'gate.io']
        symbol_map = {
            'kucoin': 'BTC-USDT',
            'gate.io': 'BTC_USDT',
        }
        all_data = fetch_all_sources_concurrently(target_sources, symbol_map, '1h')
        
        json_friendly_data = {}
        for source, df in all_data.items():
            df_reset = df.reset_index()
            df_reset['timestamp'] = df_reset['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
            json_friendly_data[source] = df_reset.to_dict('records')

        return JsonResponse(json_friendly_data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

