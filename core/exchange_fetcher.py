import requests
import os
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

load_dotenv()

class SafeRequest:
    @staticmethod
    def get(url, params=None, headers=None, retries=3, timeout=5):
        final_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        if headers: final_headers.update(headers)
        for _ in range(retries):
            try:
                response = requests.get(url, params=params, headers=final_headers, timeout=timeout)
                if response.status_code == 200: return response.json()
            except Exception: pass
        return None

# Fetcher classes are now updated to return a dictionary with price and 24h change
class KucoinFetcher:
    def fetch_ticker(self, symbol: str, **kwargs):
        data = SafeRequest.get("https://api.kucoin.com/api/v1/market/ticker", params={"symbol": symbol})
        if data and 'data' in data and data['data']['price']:
            return {
                'price': float(data['data']['price']),
                'change_24h': float(data['data'].get('changeRate', 0)) * 100
            }
        return None

class BitfinexFetcher:
    def fetch_ticker(self, symbol: str, **kwargs):
        cleaned_symbol = symbol.replace("USDT", "USD").upper()
        data = SafeRequest.get(f"https://api-pub.bitfinex.com/v2/ticker/t{cleaned_symbol}")
        if data and isinstance(data, list) and len(data) >= 7:
            return {
                'price': float(data[6]),
                'change_24h': float(data[5]) * 100
            }
        return None

class MexcFetcher:
    def __init__(self, api_key: str, **kwargs): self.api_key = api_key
    def fetch_ticker(self, symbol: str, **kwargs):
        data = SafeRequest.get("https://api.mexc.com/api/v3/ticker/24hr", params={"symbol": symbol})
        if data and 'lastPrice' in data and 'priceChangePercent' in data:
            # MEXC percent is already multiplied by 100
            return {
                'price': float(data['lastPrice']),
                'change_24h': float(data['priceChangePercent']) * 100
            }
        return None

class MultiExchangeFetcher:
    def __init__(self, source: str):
        self.source = source.lower()
        mexc_api_key = os.getenv('MEXC_API_KEY')
        if self.source == "kucoin": self.fetcher = KucoinFetcher()
        elif self.source == "bitfinex": self.fetcher = BitfinexFetcher()
        elif self.source == "mexc":
            if not mexc_api_key: raise ValueError("MEXC API key not set.")
            self.fetcher = MexcFetcher(api_key=mexc_api_key)
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
            data = fetcher.fetch_ticker(symbol=task['symbol'])
            return task['coin'], task['source'], data
        except Exception as e:
            print(f"[{task['coin']} @ {task['source']}] Fetch failed: {e}")
            return task['coin'], task['source'], None

    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        future_to_task = {executor.submit(_fetch_one, task): task for task in tasks}
        for future in as_completed(future_to_task):
            coin, source, data = future.result()
            if data is not None:
                results[coin][source] = data
    return results
