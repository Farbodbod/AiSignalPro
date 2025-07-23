import requests
import pandas as pd
import time
import os
from datetime import datetime
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

class SafeRequest:
    @staticmethod
    def get(url, params=None, headers=None, retries=3, timeout=10):
        for attempt in range(retries):
            try:
                response = requests.get(url, params=params, headers=headers, timeout=timeout)
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"[{url}] HTTP {response.status_code}: {response.text}")
            except Exception as e:
                print(f"Error fetching {url}: {e}")
            time.sleep(1)
        return None

def standardize_df(df):
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.dropna()
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.sort_values('timestamp')
    df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
    df.set_index('timestamp', inplace=True)
    return df

class CoingeckoFetcher:
    BASE_URL = "https://api.coingecko.com/api/v3"
    def fetch_ohlcv(self, coin_id: str, timeframe: str = "1h", **kwargs):
        params = {"vs_currency": "usd", "days": "30"}
        url = f"{self.BASE_URL}/coins/{coin_id}/market_chart"
        data = SafeRequest.get(url, params=params)
        if not data or 'prices' not in data:
            raise ValueError("Invalid response from Coingecko.")
        prices = pd.DataFrame(data['prices'], columns=['timestamp', 'close'])
        volumes = pd.DataFrame(data['total_volumes'], columns=['timestamp', 'volume'])
        df = prices.merge(volumes, on='timestamp')
        for col in ['open', 'high', 'low']:
            df[col] = df['close']
        return standardize_df(df)

class KucoinFetcher:
    BASE_URL = "https://api.kucoin.com"
    interval_map = {"1h": "1hour"}
    def fetch_ohlcv(self, symbol: str, timeframe: str = "1h", **kwargs):
        params = {"symbol": symbol, "type": self.interval_map.get(timeframe, "1hour")}
        data = SafeRequest.get(f"{self.BASE_URL}/api/v1/market/candles", params=params)
        if not data or 'data' not in data:
            return pd.DataFrame()
        df = pd.DataFrame(data['data'], columns=['timestamp','open','close','high','low','volume','turnover'])
        df['timestamp'] = df['timestamp'].astype(float) * 1000
        df = df.astype({'open': float, 'high': float, 'low': float, 'close': float, 'volume': float})
        return standardize_df(df)

class GateioFetcher:
    BASE_URL = "https://api.gate.io/api/v4"
    interval_map = {"1h": "1h"}
    def fetch_ohlcv(self, symbol: str, timeframe: str = "1h", **kwargs):
        params = {"currency_pair": symbol, "interval": self.interval_map.get(timeframe, "1h")}
        data = SafeRequest.get(f"{self.BASE_URL}/spot/candlesticks", params=params)
        if not data: return pd.DataFrame()
        df = pd.DataFrame(data, columns=['timestamp','volume','close','high','low','open'])
        df['timestamp'] = df['timestamp'].astype(float) * 1000
        df = df.astype({'open': float, 'high': float, 'low': float, 'close': float, 'volume': float})
        return standardize_df(df)

class OkxFetcher:
    BASE_URL = "https://www.okx.com"
    interval_map = {"1h": "1H"}
    def fetch_ohlcv(self, symbol: str, timeframe: str = "1h", **kwargs):
        params = {"instId": symbol, "bar": self.interval_map.get(timeframe, "1H")}
        data = SafeRequest.get(f"{self.BASE_URL}/api/v5/market/candles", params=params)
        if not data or 'data' not in data: return pd.DataFrame()
        df = pd.DataFrame(data['data'], columns=['timestamp','open','high','low','close','volume','volCcy'])
        df['timestamp'] = pd.to_datetime(df['timestamp']).astype(int) / 1_000_000
        df = df.astype({'open': float, 'high': float, 'low': float, 'close': float, 'volume': float})
        return standardize_df(df)

class MexcFetcher:
    BASE_URL = "https://api.mexc.com"
    interval_map = {"1h": "1h"}
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
    def fetch_ohlcv(self, symbol: str, timeframe: str = "1h", **kwargs):
        params = {"symbol": symbol, "interval": self.interval_map.get(timeframe, "1h")}
        headers = {'X-MEXC-APIKEY': self.api_key}
        data = SafeRequest.get(f"{self.BASE_URL}/api/v3/klines", params=params, headers=headers)
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data, columns=['timestamp','open','high','low','close','volume','close_time','quote_asset_volume','number_of_trades','taker_buy_base_asset_volume','taker_buy_quote_asset_volume'])
        df = df.astype({'open': float, 'high': float, 'low': float, 'close': float, 'volume': float})
        return standardize_df(df)

class BitfinexFetcher:
    BASE_URL = "https://api-pub.bitfinex.com/v2"
    interval_map = {"1h": "1h"}
    def fetch_ohlcv(self, symbol: str, timeframe: str = "1h", **kwargs):
        url = f"{self.BASE_URL}/candles/trade:{self.interval_map.get(timeframe, '1h')}:t{symbol}/hist"
        data = SafeRequest.get(url, params={"sort": 1})
        if not data: return pd.DataFrame()
        df = pd.DataFrame(data, columns=['timestamp','open','close','high','low','volume'])
        return standardize_df(df)

class CoinmarketcapFetcher:
    BASE_URL = "https://pro-api.coinmarketcap.com"
    def __init__(self, api_key: str):
        self.api_key = api_key
    def fetch_global_metrics(self):
        url = f"{self.BASE_URL}/v1/global-metrics/quotes/latest"
        headers = {"X-CMC_PRO_API_KEY": self.api_key}
        data = SafeRequest.get(url, headers=headers)
        if not data or 'data' not in data:
            raise ValueError("Invalid response from CoinMarketCap.")
        quote = data['data']['quote']['USD']
        return {
            'market_cap': quote['total_market_cap'],
            'volume_24h': quote['total_volume_24h'],
            'btc_dominance': data['data']['btc_dominance']
        }
    def fetch_ohlcv(self, **kwargs):
        raise NotImplementedError("CMC OHLCV not implemented yet.")

class MultiExchangeFetcher:
    def __init__(self, source: str):
        self.source = source.lower()
        mexc_api_key = os.getenv('MEXC_API_KEY')
        mexc_secret = os.getenv('MEXC_SECRET_KEY')
        cmc_api_key = os.getenv('CMC_API_KEY')

        if self.source == "coingecko": self.fetcher = CoingeckoFetcher()
        elif self.source == "kucoin": self.fetcher = KucoinFetcher()
        elif self.source == "gate.io": self.fetcher = GateioFetcher()
        elif self.source == "okx": self.fetcher = OkxFetcher()
        elif self.source == "mexc":
            if not mexc_api_key: raise ValueError("MEXC API key not set.")
            self.fetcher = MexcFetcher(mexc_api_key, mexc_secret or "")
        elif self.source == "bitfinex": self.fetcher = BitfinexFetcher()
        elif self.source == "coinmarketcap":
            if not cmc_api_key: raise ValueError("CMC API key not set.")
            self.fetcher = CoinmarketcapFetcher(cmc_api_key)
        else:
            raise ValueError(f"Unknown exchange source: {self.source}")

    def get_fetcher(self):
        return self.fetcher

def fetch_all_coins_concurrently(sources: List[str], symbol_map: Dict[str, Dict[str, str]], timeframe: str) -> Dict[str, Dict[str, pd.DataFrame]]:
    results = {}
    tasks = []
    for coin, mapping in symbol_map.items():
        results[coin] = {}
        for source in sources:
            if source in mapping:
                tasks.append({'coin': coin, 'source': source, 'symbol': mapping[source], 'timeframe': timeframe})

    def _fetch_one(task):
        try:
            fetcher = MultiExchangeFetcher(task['source']).get_fetcher()
            kwargs = {'timeframe': task['timeframe']}
            if task['source'] == 'coingecko':
                kwargs['coin_id'] = task['symbol']
            else:
                kwargs['symbol'] = task['symbol']
            df = fetcher.fetch_ohlcv(**kwargs)
            return task['coin'], task['source'], df
        except Exception as e:
            print(f"Failed to fetch {task.get('symbol') or task.get('coin_id')} from {task['source']}: {e}")
            return task['coin'], task['source'], pd.DataFrame()

    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        future_to_task = {executor.submit(_fetch_one, task): task for task in tasks}
        for future in as_completed(future_to_task):
            coin, source, df = future.result()
            if not df.empty:
                results[coin][source] = df
    return results
