from django.http import JsonResponse, HttpResponse
from django.core.cache import cache
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback
import os
import logging
from .exchange_fetcher import SafeRequest, fetch_all_tickers_concurrently, MultiExchangeFetcher

# IMPROVEMENT 4: Use Django's logging system instead of print()
logger = logging.getLogger(__name__)

# ===================================================================
# Helper Functions for Market Overview (with all improvements)
# ===================================================================
def fetch_from_coingecko():
    """Fetches global market data from CoinGecko with caching."""
    cache_key = "coingecko_global_data"
    cached_data = cache.get(cache_key)
    if cached_data:
        logger.info("Returning cached data for CoinGecko.")
        return cached_data

    try:
        url = "https://api.coingecko.com/api/v3/global"
        data = SafeRequest.get(url)
        if not data or 'data' not in data:
            raise ValueError('Invalid data from CoinGecko')
        
        cg_data = data['data']
        # IMPROVEMENT 2: Safer access to nested dictionary keys
        result = {
            'market_cap': cg_data.get('total_market_cap', {}).get('usd', 0),
            'volume_24h': cg_data.get('total_volume', {}).get('usd', 0),
            'btc_dominance': cg_data.get('market_cap_percentage', {}).get('btc', 0)
        }
        # IMPROVEMENT 6: Cache the successful result for 30 seconds
        cache.set(cache_key, result, 30)
        return result
    except Exception as e:
        logger.warning(f"CoinGecko fetch failed: {e}")
        raise RuntimeError(f"CoinGecko fetch failed: {e}")

def fetch_from_coinmarketcap():
    """Fetches global market data from CoinMarketCap with its own error handling."""
    # This function is already safe due to the checks in the main view
    cmc_fetcher = MultiExchangeFetcher('coinmarketcap').get_fetcher()
    return cmc_fetcher.fetch_global_metrics()

def market_overview_view(request):
    response_data = {'market_cap': 0, 'volume_24h': 0, 'btc_dominance': 0, 'fear_and_greed': 'N/A'}
    market_data = None

    try:
        market_data = fetch_from_coingecko()
    except Exception as e_cg:
        logger.warning(f"Primary source (CoinGecko) failed: {e_cg}. Trying fallback (CoinMarketCap).")
        try:
            market_data = fetch_from_coinmarketcap()
        except Exception as e_cmc:
            logger.error(f"Fallback source (CoinMarketCap) also failed: {e_cmc}.")

    if market_data and market_data.get('market_cap', 0) > 0:
        response_data.update(market_data)
    
    try:
        fng_url = "https://api.alternative.me/fng/?limit=1"
        fng_data = SafeRequest.get(fng_url)
        if fng_data and 'data' in fng_data and fng_data['data']:
            value = fng_data['data'][0].get('value', 'N/A')
            text = fng_data['data'][0].get('value_classification', 'Unknown')
            response_data['fear_and_greed'] = f"{value} ({text})"
    except Exception as e_fng:
        logger.warning(f"Could not fetch Fear & Greed index: {e_fng}")
        
    return JsonResponse(response_data)


# ===================================================================
# System Status View (with all improvements)
# ===================================================================
def check_exchange_status(exchange_info):
    name, url = exchange_info['name'], exchange_info['status_url']
    try:
        start_time = time.time()
        # IMPROVEMENT 2: Fallback from HEAD to GET request
        response = requests.head(url, timeout=5)
        if response.status_code == 405: # Method Not Allowed
            response = requests.get(url, timeout=5)
        end_time = time.time()
        
        if response.status_code == 200:
            # IMPROVEMENT 3: More precise ping timing
            ping = round((end_time - start_time) * 1000, 1)
            return {'name': name, 'status': 'online', 'ping': f'{ping}ms'}
        else:
            return {'name': name, 'status': 'offline', 'ping': f'Err {response.status_code}'}
    except requests.exceptions.RequestException:
        return {'name': name, 'status': 'offline', 'ping': '---'}

def system_status_view(request):
    exchanges_to_check = [{'name': 'Kucoin', 'status_url': 'https://api.kucoin.com/api/v1/timestamp'}, {'name': 'Gate.io', 'status_url': 'https://api.gate.io/api/v4/spot/time'}, {'name': 'MEXC', 'status_url': 'https://api.mexc.com/api/v3/time'}, {'name': 'OKX', 'status_url': 'https://www.okx.com/api/v5/system/time'}, {'name': 'Bitfinex', 'status_url': 'https://api-pub.bitfinex.com/v2/platform/status'}, {'name': 'Coingecko', 'status_url': 'https://api.coingecko.com/api/v3/ping'}]
    results = []
    with ThreadPoolExecutor(max_workers=6) as executor: # Capped workers
        futures = {executor.submit(check_exchange_status, ex): ex for ex in exchanges_to_check}
        for future in as_completed(futures):
            results.append(future.result())
    return JsonResponse(results, safe=False)


# ===================================================================
# All Data View (with all improvements)
# ===================================================================
def home_page_view(request): return HttpResponse("<h1>Django Server is Running!</h1>")

def all_data_view(request):
    try:
        target_sources = ['kucoin', 'bitfinex', 'mexc']
        symbol_map = {
            'BTC': {'kucoin':'BTC-USDT', 'bitfinex':'BTCUSD', 'mexc':'BTCUSDT'},
            'ETH': {'kucoin':'ETH-USDT', 'bitfinex':'ETHUSD', 'mexc':'ETHUSDT'},
            'XRP': {'kucoin':'XRP-USDT', 'bitfinex':'XRPUSD', 'mexc':'XRPUSDT'},
            'SOL': {'kucoin':'SOL-USDT', 'bitfinex':'SOLUSD', 'mexc':'SOLUSDT'},
            'DOGE': {'kucoin':'DOGE-USDT', 'bitfinex':'DOGEUSD', 'mexc':'DOGEUSDT'}
        }
        
        # IMPROVEMENT 5: Validate symbol_map against target_sources
        for coin, mappings in symbol_map.items():
            for source in target_sources:
                if source not in mappings:
                    raise ValueError(f"Missing symbol mapping for {coin} on exchange {source}")

        all_ticker_data = fetch_all_tickers_concurrently(target_sources, symbol_map)
        return JsonResponse(all_ticker_data)
    except Exception as e:
        logger.error(f"Error in all_data_view: {e}\n{traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)
