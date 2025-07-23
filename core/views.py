# تمام محتوای فایل را با این کد جایگزین کنید

from django.http import JsonResponse, HttpResponse
from .exchange_fetcher import fetch_all_coins_concurrently
# ... (بقیه import ها) ...
import time, traceback, requests
from concurrent.futures import ThreadPoolExecutor

# (ویوهای home_page_view, system_status_view, market_overview_view بدون تغییر باقی می‌مانند)
def home_page_view(request): return HttpResponse("<h1>Django Server is Running!</h1>")
# ...

# ویو اصلی دریافت داده‌ها که اکنون تمام صرافی‌ها را فراخوانی می‌کند
def all_data_view(request):
    try:
        # لیست کامل صرافی‌های فعال ما
        target_sources = ['coingecko', 'kucoin', 'gate.io', 'okx', 'bitfinex', 'mexc']
        
        # نقشه کامل نمادها برای ارزهای مورد نظر
        symbol_map = {
            'BTC': {
                'coingecko': 'bitcoin', 'kucoin': 'BTC-USDT', 'gate.io': 'BTC_USDT',
                'okx': 'BTC-USDT', 'bitfinex': 'BTCUSD', 'mexc': 'BTCUSDT'
            },
            'ETH': {
                'coingecko': 'ethereum', 'kucoin': 'ETH-USDT', 'gate.io': 'ETH_USDT',
                'okx': 'ETH-USDT', 'bitfinex': 'ETHUSD', 'mexc': 'ETHUSDT'
            },
            'XRP': {
                'coingecko': 'ripple', 'kucoin': 'XRP-USDT', 'gate.io': 'XRP_USDT',
                'okx': 'XRP-USDT', 'bitfinex': 'XRPUSD', 'mexc': 'XRPUSDT'
            },
            'SOL': {
                'coingecko': 'solana', 'kucoin': 'SOL-USDT', 'gate.io': 'SOL_USDT',
                'okx': 'SOL-USDT', 'bitfinex': 'SOLUSD', 'mexc': 'SOLUSDT'
            },
            'DOGE': {
                'coingecko': 'dogecoin', 'kucoin': 'DOGE-USDT', 'gate.io': 'DOGE_USDT',
                'okx': 'DOGE-USDT', 'bitfinex': 'DOGEUSD', 'mexc': 'DOGEUSDT'
            },
        }
        
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
        return JsonResponse({'error': str(e), 'traceback': traceback.format_exc()}, status=500)
