from django.http import JsonResponse, HttpResponse
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback
import os
from .exchange_fetcher import SafeRequest, fetch_all_tickers_concurrently, MultiExchangeFetcher
import logging

logger = logging.getLogger(__name__)

def market_overview_view(request):
    response_data = {'market_cap': 0, 'volume_24h': 0, 'btc_dominance': 0, 'fear_and_greed': 'N/A'}
    market_data = None
    try:
        cmc_fetcher = MultiExchangeFetcher('coinmarketcap').get_fetcher()
        market_data = cmc_fetcher.fetch_global_metrics()
    except Exception as e:
        logger.warning(f"CoinMarketCap failed: {e}. Trying CoinGecko fallback.")
        try:
            coingecko_url = "https://api.coingecko.com/api/v3/global"
            global_data = SafeRequest.get(coingecko_url)
            if global_data and 'data' in global_data:
                cg_data = global_data['data']
                market_data = {
                    'market_cap': cg_data.get('total_market_cap', {}).get('usd', 0),
                    'volume_24h': cg_data.get('total_volume', {}).get('usd', 0),
                    'btc_dominance': cg_data.get('market_cap_percentage', {}).get('btc', 0)
                }
        except Exception as e_cg:
            logger.error(f"CoinGecko fallback also failed: {e_cg}")

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

def check_exchange_status(exchange_info):
    name, url = exchange_info['name'], exchange_info['status_url']
    try:
        start_time = time.time()
        response = requests.head(url, timeout=5)
        if response.status_code == 405: # Method Not Allowed
            response = requests.get(url, timeout=5)
        end_time = time.time()
        if response.status_code == 200:
            ping = round((end_time - start_time) * 1000, 1)
            return {'name': name, 'status': 'online', 'ping': f'{ping}ms'}
        else:
            return {'name': name, 'status': 'offline', 'ping': f'Err {response.status_code}'}
    except requests.exceptions.RequestException:
        return {'name': name, 'status': 'offline', 'ping': '---'}

def system_status_view(request):
    exchanges_to_check = [{'name': 'Kucoin', 'status_url': 'https://api.kucoin.com/api/v1/timestamp'}, {'name': 'Gate.io', 'status_url': 'https://api.gate.io/api/v4/spot/time'}, {'name': 'MEXC', 'status_url': 'https://api.mexc.com/api/v3/time'}, {'name': 'OKX', 'status_url': 'https://www.okx.com/api/v5/system/time'}, {'name': 'Bitfinex', 'status_url': 'https://api-pub.bitfinex.com/v2/platform/status'}, {'name': 'Coingecko', 'status_url': 'https://api.coingecko.com/api/v3/ping'}]
    results = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(check_exchange_status, ex): ex for ex in exchanges_to_check}
        for future in as_completed(futures):
            results.append(future.result())
    return JsonResponse(results, safe=False)

def home_page_view(request):
    return HttpResponse("<h1>Django Server is Running!</h1>")

def all_data_view(request):
    try:
        target_sources = ['kucoin', 'bitfinex', 'mexc']
        symbol_map = {'BTC':{'kucoin':'BTC-USDT','bitfinex':'BTCUSD','mexc':'BTCUSDT'},'ETH':{'kucoin':'ETH-USDT','bitfinex':'ETHUSD','mexc':'ETHUSDT'},'XRP':{'kucoin':'XRP-USDT','bitfinex':'XRPUSD','mexc':'XRPUSDT'},'SOL':{'kucoin':'SOL-USDT','bitfinex':'SOLUSD','mexc':'SOLUSDT'},'DOGE':{'kucoin':'DOGE-USDT','bitfinex':'DOGEUSD','mexc':'DOGEUSDT'}}
        all_ticker_data = fetch_all_tickers_concurrently(target_sources, symbol_map)
        final_data = {}
        for coin, sources in all_ticker_data.items():
            if 'kucoin' in sources:
                final_data[coin] = {**sources['kucoin'], 'source': 'kucoin'}
            elif sources:
                first_source = list(sources.keys())[0]
                final_data[coin] = {**sources[first_source], 'source': first_source}
        return JsonResponse(final_data)
    except Exception as e:
        logger.error(f"Error in all_data_view: {e}\n{traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)
