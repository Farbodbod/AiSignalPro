import requests
import pandas as pd
import time
import os
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
import multiprocessing

load_dotenv()

class SafeRequest:
    @staticmethod
    def get(url, params=None, headers=None, retries=3, timeout=5):
        final_headers = { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36' }
        if headers: final_headers.update(headers)
        for _ in range(retries):
            try:
                response = requests.get(url, params=params, headers=final_headers, timeout=timeout)
                if response.status_code == 200: return response.json()
                else: print(f"Request failed with status {response.status_code} for {url}")
            except Exception as e: print(f"Request exception for {url}: {e}")
            time.sleep(1)
        return None

def standardize_ohlcv_df(df):
    if df is None or df.empty: return pd.DataFrame()
    df = df.dropna()
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.sort_values('timestamp')
    df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
    df.set_index('timestamp', inplace=True)
    return df

class CoingeckoFetcher:
    def fetch_ticker(self, coin_id: str, **kwargs):
        data = SafeRequest.get("https://api.coingecko.com/api/v3/simple/price", params={"ids": coin_id, "vs_currencies": "usd"})
        return data[coin_id]['usd'] if data and coin_id in data and 'usd' in data[coin_id] else None

class KucoinFetcher:
    def fetch_ticker(self, symbol: str, **kwargs):
        data = SafeRequest.get("https://api.kucoin.com/api/v1/market/ticker", params={"symbol": symbol})
        if data and 'data' in data and data['data']['price']:
            return {'price': float(data['data']['price']), 'change_24h': float(data['data'].get('changeRate', 0)) * 100}
        return None

class GateioFetcher:
    def fetch_ticker(self, symbol: str, **kwargs):
        data = SafeRequest.get("https://api.gate.io/api/v4/spot/tickers", params={"currency_pair": symbol})
        if data and len(data) > 0 and 'last' in data[0]:
            return {'price': float(data[0]['last']), 'change_24h': float(data[0].get('change_percentage', 0))}
        return None

class OkxFetcher:
    def fetch_ticker(self, symbol: str, **kwargs):
        data = SafeRequest.get("https://www.okx.com/api/v5/market/ticker", params={"instId": symbol})
        if data and 'data' in data and len(data['data']) > 0 and 'last' in data['data'][0]:
            return {'price': float(data['data'][0]['last']), 'change_24h': float(data['data'][0].get('change24h', 0)) * 100}
        return None

class MexcFetcher:
    def __init__(self, api_key: str, **kwargs): self.api_key = api_key
    def fetch_ticker(self, symbol: str, **kwargs):
        data = SafeRequest.get("https://api.mexc.com/api/v3/ticker/24hr", params={"symbol": symbol})
        if data and 'lastPrice' in data and 'priceChangePercent' in data:
            return {'price': float(data['lastPrice']), 'change_24h': float(data['priceChangePercent']) * 100}
        return None

class ToobitFetcher:
    BASE_URL = "https://api.toobit.com"
    def fetch_ticker(self, symbol: str, **kwargs):
        params = {"symbol": symbol.replace("-", "")}
        data = SafeRequest.get(f"{self.BASE_URL}/api/v1/ticker/price", params=params)
        return {'price': float(data['price']), 'change_24h': 0} if data and 'price' in data else None

class XTComFetcher:
    BASE_URL = "https://api.xt.com"
    def fetch_ticker(self, symbol: str, **kwargs):
        params = {"symbol": symbol.lower().replace("-", "_")}
        data = SafeRequest.get(f"{self.BASE_URL}/v4/public/ticker", params=params)
        if data and 'result' in data and data['result']:
            return {'price': float(data['result'][0]['p']), 'change_24h': float(data['result'][0].get('r', 0)) * 100}
        return None

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
        elif self.source == "toobit": self.fetcher = ToobitFetcher()
        elif self.source == "xt.com": self.fetcher = XTComFetcher()
        else: raise ValueError(f"Unknown exchange source: {self.source}")

    def fetch_ticker(self, **kwargs):
        return self.fetcher.fetch_ticker(**kwargs)

def fetch_all_tickers_concurrently(sources: List[str], symbol_map: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, dict]]:
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
            data = fetcher.fetch_ticker(**kwargs)
            return task['coin'], task['source'], data
        except Exception as e:
            print(f"[{task['coin']} @ {task['source']}] Fetch failed: {e}")
            return task['coin'], task['source'], None

    max_threads = min(multiprocessing.cpu_count() * 4, len(tasks), 32)
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        future_to_task = {executor.submit(_fetch_one, task): task for task in tasks}
        for future in as_completed(future_to_task):
            coin, source, data = future.result()
            if data is not None:
                results[coin][source] = data
    return results
