# ===================================================================
#           views.py - نسخه اصلاح شده برای جلوگیری از کرش
# ===================================================================

from django.http import JsonResponse
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

# ما دیگر به کدهای قدیمی و ناموجود import نمی‌کنیم
# در قدم بعدی از این کلاس جدید استفاده خواهیم کرد
from .exchange_fetcher import ExchangeFetcher

logger = logging.getLogger(__name__)

# این تابع دست نخورده باقی می‌ماند چون به کدهای دیگر وابسته نیست
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
        # استفاده از requests.head برای سرعت بیشتر
        res = requests.head(exchange_info['status_url'], timeout=5)
        # برخی سرورها به head پاسخ نمی‌دهند، با get تلاش مجدد می‌کنیم
        if res.status_code == 405: 
            res = requests.get(exchange_info['status_url'], timeout=5)
        latency = round((time.time() - start) * 1000, 1)
        if res.status_code == 200:
            return {'name': exchange_info['name'], 'status': 'online', 'ping': f"{latency}ms"}
        else:
            return {'name': exchange_info['name'], 'status': 'offline', 'ping': f"Err {res.status_code}"}
    except Exception:
        return {'name': exchange_info['name'], 'status': 'offline', 'ping': '---'}

# تابع زیر موقتا داده خالی برمیگرداند تا برنامه کرش نکند
def market_overview_view(request):
    logger.info("Market overview requested, returning placeholder data for now.")
    return JsonResponse({
        'market_cap': 0,
        'volume_24h': 0,
        'btc_dominance': 0,
        'fear_and_greed': 'N/A'
    })

# این تابع هم موقتا داده خالی برمیگرداند
def all_data_view(request):
    logger.info("All data view requested, returning empty data for now.")
    return JsonResponse({})

