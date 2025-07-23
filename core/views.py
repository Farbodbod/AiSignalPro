from django.http import JsonResponse, HttpResponse
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback
import os
from .exchange_fetcher import SafeRequest, fetch_all_tickers_concurrently, MultiExchangeFetcher

def fetch_from_coingecko():
    """Fetches global market data from CoinGecko."""
    coingecko_url = "https://api.coingecko.com/api/v3/global"
    global_data = SafeRequest.get(coingecko_url)
    if not global_data or 'data' not in global_data:
        raise ValueError('Invalid data from CoinGecko')
    
    cg_data = global_data['data']
    return {
        'market_cap': cg_data.get('total_market_cap', {}).get('usd', 0),
        'volume_24h': cg_data.get('total_volume', {}).get('usd', 0),
        'btc_dominance': cg_data.get('market_cap_percentage', {}).get('btc', 0)
    }

def fetch_from_coinmarketcap():
    """Fetches global market data from CoinMarketCap."""
    cmc_fetcher = MultiExchangeFetcher('coinmarketcap').get_fetcher()
    return cmc_fetcher.fetch_global_metrics()

def market_overview_view(request):
    response_data = {'market_cap': 0, 'volume_24h': 0, 'btc_dominance': 0, 'fear_and_greed': 'N/A'}
    
    # --- Parallel Fetching for Market Data ---
    market_data_sources = [fetch_from_coingecko, fetch_from_coinmarketcap]
    market_data = None
    
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(func) for func in market_data_sources]
        for future in as_completed(futures):
            try:
                market_data = future.result()
                if market_data:
                    break # Use the first successful result and stop waiting for others
            except Exception as e:
                print(f"A market data source failed: {e}")
    
    if market_data and market_data['market_cap'] > 0:
        response_data['market_cap'] = f"${market_data['market_cap']:,.0f}"
        response_data['volume_24h'] = f"${market_data['volume_24h']:,.0f}"
        response_data['btc_dominance'] = f"{market_data['btc_dominance']:.1f}%"
    else:
        response_data['market_cap'] = 'N/A'
        response_data['volume_24h'] = 'N/A'
        response_data['btc_dominance'] = 'N/A'

    # --- Fetch Fear & Greed Index (separately) ---
    try:
        fng_url = "https://api.alternative.me/fng/?limit=1"
        fng_data = SafeRequest.get(fng_url)
        if fng_data and 'data' in fng_data and fng_data['data']:
            value = fng_data['data'][0]['value']
            text = fng_data['data'][0]['value_classification']
            response_data['fear_and_greed'] = f"{value} ({text})"
    except Exception as e_fng:
        print(f"Could not fetch Fear & Greed index: {e_fng}")
        
    return JsonResponse(response_data)


# ===================================================================
# Other views (no changes)
# ===================================================================
def check_exchange_status(exchange_info):
    name = exchange_info['name']; url = exchange_info['status_url']
    try:
        start_time = time.time(); response = requests.head(url, timeout=5); end_time = time.time()
        if response.status_code == 200:
            ping = int((end_time - start_time) * 1000)
            return {'name': name, 'status': 'online', 'ping': f'{ping}ms'}
        else: return {'name': name, 'status': 'offline', 'ping': 'Error'}
    except requests.exceptions.RequestException: return {'name': name, 'status': 'offline', 'ping': '---'}

def system_status_view(request):
    exchanges_to_check = [{'name': 'Kucoin', 'status_url': 'https://api.kucoin.com/api/v1/timestamp'},{'name': 'Gate.io', 'status_url': 'https://api.gate.io/api/v4/spot/time'},{'name': 'MEXC', 'status_url': 'https://api.mexc.com/api/v3/time'},{'name': 'OKX', 'status_url': 'https://www.okx.com/api/v5/system/time'},{'name': 'Bitfinex', 'status_url': 'https://api-pub.bitfinex.com/v2/platform/status'},{'name': 'Coingecko', 'status_url': 'https://api.coingecko.com/api/v3/ping'}]
    results = [];
    with ThreadPoolExecutor(max_workers=len(exchanges_to_check)) as executor:
        futures = {executor.submit(check_exchange_status, ex): ex for ex in exchanges_to_check}
        for future in futures: results.append(future.result())
    return JsonResponse(results, safe=False)

def home_page_view(request): return HttpResponse("<h1>Django Server is Running!</h1>")

def all_data_view(request):
    try:
        target_sources = ['coingecko', 'kucoin', 'gate.io', 'okx', 'bitfinex', 'mexc']
        symbol_map = {'BTC':{'coingecko':'bitcoin','kucoin':'BTC-USDT','gate.io':'BTC_USDT','okx':'BTC-USDT','bitfinex':'BTCUSD','mexc':'BTCUSDT'},'ETH':{'coingecko':'ethereum','kucoin':'ETH-USDT','gate.io':'ETH_USDT','okx':'ETH-USDT','bitfinex':'ETHUSD','mexc':'ETHUSDT'},'XRP':{'coingecko':'ripple','kucoin':'XRP-USDT','gate.io':'XRP_USDT','okx':'XRP-USDT','bitfinex':'XRPUSD','mexc':'XRPUSDT'},'SOL':{'coingecko':'solana','kucoin':'SOL-USDT','gate.io':'SOL_USDT','okx':'SOL-USDT','bitfinex':'SOLUSD','mexc':'SOLUSDT'},'DOGE':{'coingecko':'dogecoin','kucoin':'DOGE-USDT','gate.io':'DOGE_USDT','okx':'DOGE-USDT','bitfinex':'DOGEUSD','mexc':'DOGEUSDT'}}
        all_ticker_data = fetch_all_tickers_concurrently(target_sources, symbol_map)
        return JsonResponse(all_ticker_data)
    except Exception as e:
        return JsonResponse({'error': str(e), 'traceback': traceback.format_exc()}, status=500)
