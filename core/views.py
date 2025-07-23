from django.http import JsonResponse, HttpResponse
from .exchange_fetcher import fetch_all_sources_concurrently
import pandas as pd

# ویو تست قبلی ما برای آدرس ریشه
def home_page_view(request):
    return HttpResponse("<h1>Django Server is Running!</h1>")

# ویو قدیمی که دیگر به آن نیاز نداریم اما برای مرجع نگه می‌داریم
def system_status_view(request):
    data = [
      { "name": 'Kucoin', "status": 'online', "ping": '120ms' },
      { "name": 'Gate.io', "status": 'online', "ping": '180ms' },
    ]
    return JsonResponse(data, safe=False)

# ویو جدید و اصلی ما که از موتور جدید استفاده می‌کند
def all_data_view(request):
    try:
        target_sources = ['kucoin', 'gate.io']
        symbol_map = {
            'kucoin': 'BTC-USDT',
            'gate.io': 'BTC_USDT',
        }
        
        # فراخوانی تابع دریافت همزمان دیتا
        all_data = fetch_all_sources_concurrently(target_sources, symbol_map, '1h')
        
        # تبدیل دیتافریم‌های پانداز به فرمت JSON
        json_friendly_data = {}
        for source, df in all_data.items():
            df_reset = df.reset_index()
            df_reset['timestamp'] = df_reset['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
            json_friendly_data[source] = df_reset.to_dict('records')

        return JsonResponse(json_friendly_data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
