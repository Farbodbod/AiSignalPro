# Replace the entire content of core/views.py with this code

from django.http import JsonResponse, HttpResponse
import requests
import time
from concurrent.futures import ThreadPoolExecutor
import traceback
import os
from .exchange_fetcher import SafeRequest, fetch_all_tickers_concurrently, MultiExchangeFetcher

def fetch_from_coingecko():
    # ... (code from previous step)
def fetch_from_coinmarketcap():
    # ... (code from previous step)
def market_overview_view(request):
    # ... (code from previous step)

def check_telegram_status():
    """Checks the status of the Telegram bot using the getMe method."""
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        return {'name': 'Telegram', 'status': 'offline', 'ping': 'No Token'}
    
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        start_time = time.time()
        response = requests.get(url, timeout=5)
        end_time = time.time()
        if response.status_code == 200 and response.json().get('ok'):
            ping = int((end_time - start_time) * 1000)
            return {'name': 'Telegram', 'status': 'online', 'ping': f'{ping}ms'}
        else:
            return {'name': 'Telegram', 'status': 'offline', 'ping': 'Error'}
    except requests.exceptions.RequestException:
        return {'name': 'Telegram', 'status': 'offline', 'ping': '---'}

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
    with ThreadPoolExecutor(max_workers=len(exchanges_to_check) + 1) as executor:
        # Submit exchange checks
        futures = [executor.submit(check_exchange_status, ex) for ex in exchanges_to_check]
        # Submit Telegram check
        futures.append(executor.submit(check_telegram_status))
        
        for future in as_completed(futures):
            results.append(future.result())
            
    return JsonResponse(results, safe=False)

# ... (The rest of the views like home_page_view and all_data_view remain unchanged) ...
def home_page_view(request): return HttpResponse("<h1>Django Server is Running!</h1>")
def all_data_view(request): # ... (code from previous step)
