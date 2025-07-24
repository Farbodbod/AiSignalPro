import requests
import pandas as pd
import time
import os
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
import multiprocessing # For optimizing thread count

load_dotenv()

class SafeRequest:
    @staticmethod
    def get(url, params=None, headers=None, retries=3, timeout=5):
        final_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        if headers:
            final_headers.update(headers)
        for _ in range(retries):
            try:
                response = requests.get(url, params=params, headers=final_headers, timeout=timeout)
                if response.status_code == 200:
                    return response.json()
                else:
                    # IMPROVEMENT 1: Log non-200 status codes
                    print(f"Request failed with status code {response.status_code} for URL: {url}")
            except Exception as e:
                print(f"Request exception for URL {url}: {e}")
                time.sleep(1)
        return None

# ... (CoingeckoFetcher, KucoinFetcher, OkxFetcher are fine as is) ...
class CoingeckoFetcher:
    def fetch_ticker(self, coin_id: str, **kwargs):
        # ...
class KucoinFetcher:
    def fetch_ticker(self, symbol: str, **kwargs):
        # ...
class GateioFetcher:
    def fetch_ticker(self, symbol: str, **kwargs):
        # ...
class OkxFetcher:
    def fetch_ticker(self, symbol: str, **kwargs):
        # ...

class MexcFetcher:
    def __init__(self, api_key: str, **kwargs): self.api_key = api_key
    def fetch_ticker(self, symbol: str, **kwargs):
        url = "https://api.mexc.com/api/v3/ticker/price"
        params = {"symbol": symbol}
        headers = {'X-MEXC-APIKEY': self.api_key}
        data = SafeRequest.get(url, params=params, headers=headers)
        
        # IMPROVEMENT 3: Better error handling for MEXC
        if data is None:
            print(f"[MEXC] No response for symbol: {symbol}")
            return None
        elif 'price' not in data:
            print(f"[MEXC] Invalid response format for symbol {symbol}: {data}")
            return None
        return float(data['price'])

class BitfinexFetcher:
    def fetch_ticker(self, symbol: str, **kwargs):
        # IMPROVEMENT 2: Safer symbol conversion
        if symbol.endswith("USDT"):
            cleaned_symbol = symbol.replace("USDT", "USD")
        else:
            cleaned_symbol = symbol.upper()
            
        url = f"https://api-pub.bitfinex.com/v2/ticker/t{cleaned_symbol}"
        data = SafeRequest.get(url)
        return float(data[6]) if data and isinstance(data, list) and len(data) >= 7 else None

class MultiExchangeFetcher:
    # ... (No changes needed here) ...
    def __init__(self, source: str): #...
    def fetch_ticker(self, **kwargs): #...

def fetch_all_tickers_concurrently(sources: List[str], symbol_map: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, float]]:
    results = {}
    tasks = []
    for coin, mapping in symbol_map.items():
        results[coin] = {}
        for source in sources:
            if source in mapping:
                tasks.append({'coin': coin, 'source': source, 'symbol': mapping[source]})

    def _fetch_one(task):
        try:
            fetcher = MultiExchangeFetcher(task['source'])
            # IMPROVEMENT 5: More readable kwargs logic
            if task['source'] == 'coingecko':
                kwargs = {'coin_id': task['symbol']}
            else:
                kwargs = {'symbol': task['symbol']}
            
            price = fetcher.fetch_ticker(**kwargs)
            return task['coin'], task['source'], price
        except Exception as e:
            print(f"[{task['coin']} @ {task['source']}] Fetch failed: {e}")
            return task['coin'], task['source'], None

    # IMPROVEMENT 4: Dynamic and safe thread count
    max_threads = min(multiprocessing.cpu_count() * 2, len(tasks), 20)
    
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        future_to_task = {executor.submit(_fetch_one, task): task for task in tasks}
        for future in as_completed(future_to_task):
            coin, source, price = future.result()
            if price is not None:
                results[coin][source] = price
    return results
