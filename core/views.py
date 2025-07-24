from django.http import JsonResponse
from .exchange_fetcher import fetch_all_tickers_concurrently
import traceback
# (بقیه import ها و ویوهای غیرمرتبط مانند system_status حذف شده‌اند)

def all_data_view(request):
    try:
        target_sources = ['kucoin', 'bitfinex', 'mexc']
        priority_source = 'kucoin'
        
        symbol_map = {
            'BTC': {'kucoin': 'BTC-USDT', 'bitfinex': 'BTCUSD', 'mexc': 'BTCUSDT'},
            'ETH': {'kucoin': 'ETH-USDT', 'bitfinex': 'ETHUSD', 'mexc': 'ETHUSDT'},
            'XRP': {'kucoin': 'XRP-USDT', 'bitfinex': 'XRPUSD', 'mexc': 'XRPUSDT'},
            'SOL': {'kucoin': 'SOL-USDT', 'bitfinex': 'SOLUSD', 'mexc': 'SOLUSDT'},
            'DOGE': {'kucoin': 'DOGE-USDT', 'bitfinex': 'DOGEUSD', 'mexc': 'DOGEUSDT'},
        }
        
        all_ticker_data = fetch_all_tickers_concurrently(target_sources, symbol_map)
        
        final_data = {}
        for coin, sources in all_ticker_data.items():
            # انتخاب هوشمند بر اساس اولویت
            if priority_source in sources:
                final_data[coin] = {**sources[priority_source], 'source': priority_source}
            elif sources:
                first_available_source = list(sources.keys())[0]
                final_data[coin] = {**sources[first_available_source], 'source': first_available_source}

        return JsonResponse(final_data)
        
    except Exception as e:
        return JsonResponse({'error': str(e), 'traceback': traceback.format_exc()}, status=500)

# (شما می‌توانید ویوهای دیگر مانند system_status_view را برای عملکردهای دیگر نگه دارید)
