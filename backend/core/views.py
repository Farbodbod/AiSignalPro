from django.http import JsonResponse, HttpResponse
import time
import logging
import traceback
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

from .exchange_fetcher import (
    SafeRequest,
    fetch_all_tickers_concurrently,
    MultiExchangeFetcher
)

logger = logging.getLogger(__name__)

def market_overview_view(request):
    response_data = {
        'market_cap': 0,
        'volume_24h': 0,
        'btc_dominance': 0,
        'fear_and_greed': 'N/A'
    }
    try:
        cmc_fetcher = MultiExchangeFetcher('coinmarketcap').get_fetcher()
        market_data = cmc_fetcher.fetch_global_metrics()
        if market_data:
            response_data.update(market_data)
    except Exception as e_cmc:
        logger.warning(f"[CoinMarketCap] failed: {e_cmc}")
        try:
            coingecko_url = "https://api.coingecko.com/api/v3/global"
            cg_data = SafeRequest.get(coingecko_url)
            if cg_data and 'data' in cg_data:
                data = cg_data['data']
                response_data.update({
                    'market_cap': data.get('total_market_cap', {}).get('usd', 0),
                    'volume_24h': data.get('total_volume', {}).get('usd', 0),
                    'btc_dominance': data.get('market_cap_percentage', {}).get('btc', 0)
                })
        except Exception as e_cg:
            logger.error(f"[CoinGecko] fallback failed: {e_cg}")

    try:
        fng_url = "https://api.alternative.me/fng/?limit=1"
        fng_data = SafeRequest.get(fng_url)
        if fng_data and 'data' in fng_data and fng_data['data']:
            value = fng_data['data'][0].get('value', 'N/A')
            text = fng_data['data'][0].get('value_classification', 'Unknown')
            response_data['fear_and_greed'] = f"{value} ({text})"
    except Exception as e_fng:
        logger.warning(f"[FNG] fetch failed: {e_fng}")

    return JsonResponse(response_data)

def check_exchange_status(exchange_info):
    try:
        start = time.time()
        res = requests.head(exchange_info['status_url'], timeout=5)
        if res.status_code == 405:
            res = requests.get(exchange_info['status_url'], timeout=5)
        latency = round((time.time() - start) * 1000, 1)
        if res.status_code == 200:
            return {'name': exchange_info['name'], 'status': 'online', 'ping': f"{latency}ms"}
        else:
            return {'name': exchange_info['name'], 'status': 'offline', 'ping': f"Err {res.status_code}"}
    except Exception:
        return {'name': exchange_info['name'], 'status': 'offline', 'ping': '---'}

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

def all_data_view(request):
    try:
        sources = ['kucoin', 'mexc', 'gate.io', 'okx', 'toobit', 'xt.com']
        symbol_map = {
            'BTC': {
                'kucoin': 'BTC-USDT', 'mexc': 'BTCUSDT', 'gate.io': 'BTC_USDT',
                'okx': 'BTC-USDT', 'toobit': 'BTCUSDT', 'xt.com': 'btc_usdt'
            },
            'ETH': {
                'kucoin': 'ETH-USDT', 'mexc': 'ETHUSDT', 'gate.io': 'ETH_USDT',
                'okx': 'ETH-USDT', 'toobit': 'ETHUSDT', 'xt.com': 'eth_usdt'
            },
            'XRP': {
                'kucoin': 'XRP-USDT', 'mexc': 'XRPUSDT', 'gate.io': 'XRP_USDT',
                'okx': 'XRP-USDT', 'toobit': 'XRPUSDT', 'xt.com': 'xrp_usdt'
            },
            'SOL': {
                'kucoin': 'SOL-USDT', 'mexc': 'SOLUSDT', 'gate.io': 'SOL_USDT',
                'okx': 'SOL-USDT', 'toobit': 'SOLUSDT', 'xt.com': 'sol_usdt'
            },
            'DOGE': {
                'kucoin': 'DOGE-USDT', 'mexc': 'DOGEUSDT', 'gate.io': 'DOGE_USDT',
                'okx': 'DOGE-USDT', 'toobit': 'DOGEUSDT', 'xt.com': 'doge_usdt'
            },
        }
        all_data = fetch_all_tickers_concurrently(sources, symbol_map)
        prioritized_data = {}
        for coin, ex_data in all_data.items():
            if 'kucoin' in ex_data:
                prioritized_data[coin] = {**ex_data['kucoin'], 'source': 'kucoin'}
            elif ex_data:
                first_src = next(iter(ex_data))
                prioritized_data[coin] = {**ex_data[first_src], 'source': first_src}
        return JsonResponse(prioritized_data)
    except Exception as e:
        logger.error(f"Error in all_data_view: {e}\n{traceback.format_exc()}")
        return JsonResponse({'error': 'Internal server error'}, status=500)
