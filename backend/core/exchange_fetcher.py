import requests
import pandas as pd
import time
import os
import random
import logging
import multiprocessing
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

# Use Python's logging for better debugging in production
logger = logging.getLogger(__name__)

# Load environment variables for local development
load_dotenv()

# ===================================================================
# Helper function to format symbols for each specific exchange
# ===================================================================
def format_symbol(source: str, base_coin: str, quote_coin: str = "USDT") -> str:
    """Formats a coin pair into the specific string required by an exchange."""
    base = base_coin.upper()
    quote = quote_coin.upper()
    
    if source in ["mexc", "toobit"]:
        return f"{base}{quote}"
    if source in ["gate.io", "xt.com"]:
        return f"{base.lower()}_{quote.lower()}"
    if source == "bitfinex":
        # Bitfinex primarily uses USD, so we convert USDT to USD for this source
        if quote == "USDT":
            quote = "USD"
        return f"{base}{quote}"
    # Default format for Kucoin, OKX, etc.
    return f"{base}-{quote}"

# ===================================================================
# A robust class for making safe HTTP requests
# ===================================================================
class SafeRequest:
    @staticmethod
    def get(url, params=None, headers=None, retries=3, timeout=8):
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
                    # Log non-200 status codes for better debugging
                    logger.warning(f"Request to {url} failed with status {response.status_code}: {response.text}")
            except Exception as e:
                logger.error(f"Request exception for URL {url}: {e}")
                time.sleep(1)
        return None

# ===================================================================
# Individual Fetcher Classes for each Exchange
# ===================================================================
class CoingeckoFetcher:
    def fetch_ticker(self, coin_id: str, **kwargs) -> Optional[Dict[str, float]]:
        data = SafeRequest.get("https://api.coingecko.com/api/v3/simple/price", params={"ids": coin_id, "vs_currencies": "usd"})
        if data and data.get(coin_id, {}).get('usd'):
            return {'price': float(data[coin_id]['usd']), 'change_24h': None}
        return None

class KucoinFetcher:
    def fetch_ticker(self, symbol: str, **kwargs) -> Optional[Dict[str, float]]:
        data = SafeRequest.get("https://api.kucoin.com/api/v1/market/ticker", params={"symbol": symbol})
        if data and data.get('data') and data['data'].get('price'):
            return {
                'price': float(data['data']['price']),
                'change_24h': float(data['data'].get('changeRate', 0)) * 100
            }
        return None

class GateioFetcher:
    def fetch_ticker(self, symbol: str, **kwargs) -> Optional[Dict[str, float]]:
        data = SafeRequest.get("https://api.gate.io/api/v4/spot/tickers", params={"currency_pair": symbol})
        if data and isinstance(data, list) and len(data) > 0 and data[0].get('last'):
            return {
                'price': float(data[0]['last']),
                'change_24h': float(data[0].get('change_percentage', 0))
            }
        return None

class OkxFetcher:
    def fetch_ticker(self, symbol: str, **kwargs) -> Optional[Dict[str, float]]:
        data = SafeRequest.get("https://www.okx.com/api/v5/market/ticker", params={"instId": symbol})
        if data and data.get('data') and isinstance(data['data'], list) and len(data['data']) > 0 and data['data'][0].get('last'):
            return {
                'price': float(data['data'][0]['last']),
                'change_24h': float(data['data'][0].get('chg24h', 0)) * 100
            }
        return None
        
class MexcFetcher:
    def __init__(self, api_key: str, **kwargs): self.api_key = api_key
    def fetch_ticker(self, symbol: str, **kwargs) -> Optional[Dict[str, float]]:
        data = SafeRequest.get("https://api.mexc.com/api/v3/ticker/24hr", params={"symbol": symbol})
        if data is None:
            logger.warning(f"[MEXC] No response for symbol: {symbol}")
            return None
        item = data[0] if isinstance(data, list) else data
        if item and item.get('lastPrice') and item.get('priceChangePercent'):
             return {'price': float(item['lastPrice']), 'change_24h': float(item['priceChangePercent']) * 100}
        logger.warning(f"[MEXC] Invalid response format for symbol {symbol}: {data}")
        return None

class BitfinexFetcher:
    def fetch_ticker(self, symbol: str, **kwargs) -> Optional[Dict[str, float]]:
        data = SafeRequest.get(f"https://api-pub.bitfinex.com/v2/ticker/t{symbol}")
        if data and isinstance(data, list) and len(data) >= 7:
            return {'price': float(data[6]), 'change_24h': float(data[5]) * 100}
        return None

class ToobitFetcher:
    def fetch_ticker(self, symbol: str, **kwargs) -> Optional[Dict[str, float]]:
        data = SafeRequest.get("https://api.toobit.com/api/v1/ticker/price", params={"symbol": symbol})
        return {'price': float(data['price']), 'change_24h': None} if data and data.get('price') else None

class XTComFetcher:
    def fetch_ticker(self, symbol: str, **kwargs) -> Optional[Dict[str, float]]:
        data = SafeRequest.get("https://api.xt.com/v4/public/ticker", params={"symbol": symbol})
        if data and data.get('result') and isinstance(data['result'], list) and len(data['result']) > 0:
            item = data['result'][0]
            return {'price': float(item.get('p', 0)), 'change_24h': float(item.get('r', 0)) * 100}
        return None

# ===================================================================
# Main Fetcher Logic (Dispatcher)
# ===================================================================
class MultiExchangeFetcher:
    def __init__(self, source: str):
        self.source = source.lower()
        mexc_api_key = os.getenv('MEXC_API_KEY')
        fetcher_map = {
            "coingecko": CoingeckoFetcher, "kucoin": KucoinFetcher,
            "gate.io": GateioFetcher, "okx": OkxFetcher, "bitfinex": BitfinexFetcher,
            "toobit": ToobitFetcher, "xt.com": XTComFetcher
        }
        if self.source in fetcher_map:
            self.fetcher = fetcher_map[self.source]()
        elif self.source == "mexc":
            if not mexc_api_key: raise ValueError("MEXC API key not set in environment.")
            self.fetcher = MexcFetcher(api_key=mexc_api_key)
        else:
            raise ValueError(f"Unknown exchange source: {self.source}")

    def fetch_ticker(self, **kwargs):
        return self.fetcher.fetch_ticker(**kwargs)

# ===================================================================
# Main Concurrent Fetching Function
# ===================================================================
def fetch_all_tickers_concurrently(sources: List[str], symbol_map: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, dict]]:
    results = {}
    tasks = []
    for coin, mapping in symbol_map.items():
        results[coin] = {}
        for source in sources:
            if source in mapping:
                symbol = format_symbol(source, coin) if source != 'coingecko' else mapping[source]
                tasks.append({'coin': coin, 'source': source, 'symbol': symbol})

    def _fetch_one(task):
        try:
            time.sleep(random.uniform(0, 0.5)) # Random delay to avoid rate limiting
            fetcher = MultiExchangeFetcher(task['source'])
            
            if task['source'] == 'coingecko':
                kwargs = {'coin_id': task['symbol']}
            else:
                kwargs = {'symbol': task['symbol']}

            data = fetcher.fetch_ticker(**kwargs)
            return task['coin'], task['source'], data
        except Exception as e:
            logger.error(f"[{task['coin']} @ {task['source']}] Fetch failed: {e}")
            return task['coin'], task['source'], None

    max_threads = min(multiprocessing.cpu_count() * 2, len(tasks), 20)
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        future_to_task = {executor.submit(_fetch_one, task): task for task in tasks}
        for future in as_completed(future_to_task):
            coin, source, data = future.result()
            if data is not None:
                results[coin][source] = data
    return results
