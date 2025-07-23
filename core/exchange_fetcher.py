import requests
import pandas as pd
import time
import os
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

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
            except Exception:
                time.sleep(1)
        return None

class CoingeckoFetcher:
    def fetch_ticker(self, coin_id: str, **kwargs):
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {"ids": coin_id, "vs_currencies": "usd"}
        data = SafeRequest.get(url, params=params)
        return data[coin_id]['usd'] if data and coin_id in data and 'usd' in data[coin_id] else None

class KucoinFetcher:
    def fetch_ticker(self, symbol: str, **kwargs):
        url = "https://api.kucoin.com/api/v1/market/ticker"
        params = {"symbol": symbol}
        data = SafeRequest.get(url, params=params)
        return float(data['data']['price']) if data and 'data' in data and data['data']['price'] else None

class GateioFetcher:
    def fetch_ticker(self, symbol: str, **kwargs):
        url = "https://api.gate.io/api/v4/spot/tickers"
        params = {"currency_pair": symbol}
        data = SafeRequest.get(url, params=params)
        return float(data[0]['last']) if data and len(data) > 0 and 'last' in data[0] else None

class OkxFetcher:
    def fetch_ticker(self, symbol: str, **kwargs):
        url = "https://www.okx.com/api/v5/market/ticker"
        params = {"instId": symbol}
        data = SafeRequest.get(url, params=params)
        return float(data['data'][0]['last']) if data and 'data' in data and len(data['data']) > 0 and 'last' in data['data'][0] else None
        
class MexcFetcher:
    def __init__(self, api_key: str, **kwargs): self.api_key = api_key
    def fetch_ticker(self, symbol: str, **kwargs):
        url = "https://api.mexc.com/api/v3/ticker/price"
        params = {"symbol": symbol}
        headers = {'X-MEXC-APIKEY': self.api_key}
        data = SafeRequest.get(url, params=params, headers=headers)
        return float(data['price']) if data and 'price' in data else None

class BitfinexFetcher:
    def fetch_ticker(self, symbol: str, **kwargs):
        url = f"https://api-pub.bitfinex.com/v2/ticker/t{symbol}"
        data = SafeRequest.get(url)
        return float(data[6]) if data and isinstance(data, list) and len(data) >= 7 else None

class MultiExchangeFetcher:
    def __init__(self, source: str):
        self.source = source.lower()
        mexc_api_key = os.getenv('MEXC_API_KEY')
        if self.source == "coingecko": self.fetcher = CoingeckoFetcher()
        elif self.source == "kucoin": self.fetcher = KucoinFetcher()
        elif self.source == "gate.io": self.fetcher = GateioFetcher()
        elif self.source == "okx": self.fetcher = OkxFetcher()
        elif self.source == "mexc":
            if not mexc_api_key: raise ValueError("MEXC API key not set.")
            self.fetcher = MexcFetcher(api_key=mexc_api_key)
        elif self.source == "bitfinex": self.fetcher = BitfinexFetcher()
        else: raise ValueError(f"Unknown exchange source: {self.source}")

    def fetch_ticker(self, **kwargs):
        return self.fetcher.fetch_ticker(**kwargs)

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
            kwargs = {'coin_id' if task['source'] == 'coingecko' else 'symbol': task['symbol']}
            price = fetcher.fetch_ticker(**kwargs)
            return task['coin'], task['source'], price
        except Exception:
            return task['coin'], task['source'], None

    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        future_to_task = {executor.submit(_fetch_one, task): task for task in tasks}
        for future in as_completed(future_to_task):
            coin, source, price = future.result()
            if price is not None:
                results[coin][source] = price
    return results
