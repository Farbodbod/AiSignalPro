import requests
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import pandas as pd

logging.basicConfig(level=logging.INFO)
session = requests.Session()

class ExchangeFetcher:
    def __init__(self):
        self.base_urls = {
            "mexc": "https://api.mexc.com",
            "kucoin": "https://api.kucoin.com",
            "gateio": "https://api.gate.io",
            "okx": "https://www.okx.com",
        }
        self.interval_map = {
            'kucoin': {'1m': '1min', '1h': '1hour', '4h': '4hour', '1d': '1day'},
            'mexc': {'1m': '1m', '1h': '1h', '4h': '4h', '1d': '1d'},
            'okx': {'1m': '1m', '1h': '1H', '4h': '4H', '1d': '1D'},
        }

    def _safe_request(self, url, params=None, timeout=10):
        try:
            response = session.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.warning(f"Failed to fetch {url}: {e}")
            return None

    def get_kucoin_ticker(self, symbol='BTC-USDT'):
        url = f"{self.base_urls['kucoin']}/api/v1/market/stats?symbol={symbol}"
        data = self._safe_request(url)
        if data and data.get('data'):
            ticker = data['data']
            return {'symbol': symbol, 'price': float(ticker.get('last', 0)), 'change_24h': float(ticker.get('changeRate', 0)) * 100}
        return None

    def get_mexc_ticker(self, symbol='BTCUSDT'):
        url = f"{self.base_urls['mexc']}/api/v3/ticker/24hr?symbol={symbol}"
        data = self._safe_request(url)
        if data:
            return {'symbol': symbol, 'price': float(data.get('lastPrice', 0)), 'change_24h': float(data.get('priceChangePercent', 0)) * 100}
        return None

    def get_gateio_ticker(self, symbol='BTC_USDT'):
        logging.warning("Gate.io fetcher is currently disabled due to persistent SSL errors.")
        return None

    def get_okx_ticker(self, symbol='BTC-USDT'):
        url = f"{self.base_urls['okx']}/api/v5/market/ticker?instId={symbol}"
        data = self._safe_request(url)
        if data and data.get('data'):
            ticker = data['data'][0]
            return {'symbol': symbol, 'price': float(ticker.get('last', 0)), 'change_24h': float(ticker.get('chg24h', 0))}
        return None

    def get_klines(self, source, symbol, interval='1h', limit=200):
        source = source.lower()
        if source not in self.base_urls:
            raise ValueError(f"Source '{source}' is not supported.")
        
        interval_str = self.interval_map.get(source, {}).get(interval, interval)
        
        if source == 'kucoin':
            url = f"{self.base_urls[source]}/api/v1/market/candles"
            params = {'symbol': symbol, 'type': interval_str, 'limit': limit}
            data = self._safe_request(url, params=params)
            if data and data.get('data'):
                return [{'timestamp': int(k[0]), 'open': float(k[1]), 'high': float(k[2]), 'low': float(k[3]), 'close': float(k[4]), 'volume': float(k[5])} for k in data['data']]

        elif source == 'mexc':
            url = f"{self.base_urls[source]}/api/v3/klines"
            params = {"symbol": symbol.replace("-", ""), "interval": interval_str, "limit": limit}
            data = self._safe_request(url, params=params)
            if data:
                return [{"timestamp": int(k[0]), "open": float(k[1]), "high": float(k[2]), "low": float(k[3]), "close": float(k[4]), "volume": float(k[5])} for k in data]

        elif source == 'okx':
            url = f"{self.base_urls[source]}/api/v5/market/candles"
            params = {"instId": symbol, "bar": interval_str, "limit": limit}
            data = self._safe_request(url, params=params)
            if data and "data" in data:
                return [{"timestamp": int(k[0]), "open": float(k[1]), "high": float(k[2]), "low": float(k[3]), "close": float(k[4]), "volume": float(k[5])} for k in data['data']]
                
        return []

    def fetch_all_tickers_concurrently(self, sources, symbol_map):
        all_data = {coin: {} for coin in symbol_map.keys()}
        fetch_functions = {'kucoin': self.get_kucoin_ticker, 'mexc': self.get_mexc_ticker, 'gateio': self.get_gateio_ticker, 'okx': self.get_okx_ticker}

        with ThreadPoolExecutor(max_workers=len(sources) * len(symbol_map)) as executor:
            future_to_task = {}
            for source in sources:
                if source in fetch_functions:
                    for coin, symbols in symbol_map.items():
                        if source in symbols:
                            future = executor.submit(fetch_functions[source], symbols[source])
                            future_to_task[future] = (coin, source)

            for future in as_completed(future_to_task):
                coin, source = future_to_task[future]
                try:
                    result = future.result()
                    if result and result.get('price') > 0:
                        all_data[coin][source] = result
                except Exception as e:
                    logging.error(f"Error fetching {source} for {coin}: {e}")
        return all_data
