# تمام محتوای فایل را با این کد جایگزین کنید

import requests
import pandas as pd
import time
import os
from datetime import datetime
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

# ... (کلاس SafeRequest و تابع standardize_df بدون تغییر) ...
class SafeRequest:
    @staticmethod
    def get(url, params=None, headers=None, retries=3, timeout=10):
        # ... (کد قبلی) ...
        for attempt in range(retries):
            try:
                response = requests.get(url, params=params, headers=headers, timeout=timeout)
                if response.status_code == 200: return response.json()
                else: print(f"[{url}] HTTP {response.status_code}: {response.text}")
            except Exception as e: print(f"Error fetching {url}: {e}")
            time.sleep(1)
        return None
def standardize_df(df):
    if df is None or df.empty: return pd.DataFrame()
    # ... (بقیه کد) ...
    df = df.dropna()
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.sort_values('timestamp')
    df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
    df.set_index('timestamp', inplace=True)
    return df

# ... (تمام کلاس‌های Fetcher مانند KucoinFetcher, GateioFetcher و... بدون تغییر باقی می‌مانند) ...
class CoingeckoFetcher:
    # ...
    BASE_URL = "https://api.coingecko.com/api/v3"
    def fetch_ohlcv(self, coin_id: str, timeframe: str = "1h", **kwargs):
        params = {"vs_currency": "usd", "days": "30"}
        url = f"{self.BASE_URL}/coins/{coin_id}/market_chart"
        data = SafeRequest.get(url, params=params)
        if not data or 'prices' not in data: raise ValueError("Invalid response from Coingecko.")
        prices = pd.DataFrame(data['prices'], columns=['timestamp', 'close'])
        volumes = pd.DataFrame(data['total_volumes'], columns=['timestamp', 'volume'])
        df = prices.merge(volumes, on='timestamp')
        for col in ['open', 'high', 'low']: df[col] = df['close']
        return standardize_df(df)
class KucoinFetcher:
    # ... (کد قبلی) ...
    BASE_URL = "https://api.kucoin.com"; interval_map = {"1h": "1hour"}
    def fetch_ohlcv(self, symbol: str, timeframe: str = "1h", **kwargs):
        params = {"symbol": symbol, "type": self.interval_map.get(timeframe, "1hour")}
        data = SafeRequest.get(f"{self.BASE_URL}/api/v1/market/candles", params=params)
        if not data or 'data' not in data: return pd.DataFrame()
        df = pd.DataFrame(data['data'], columns=['timestamp','open','close','high','low','volume','turnover'])
        df['timestamp'] = df['timestamp'].astype(float) * 1000
        df = df.astype({'open': float, 'high': float, 'low': float, 'close': float, 'volume': float})
        return standardize_df(df)
class MexcFetcher:
    BASE_URL = "https://api.mexc.com"; interval_map = {"1h": "1h"}
    def __init__(self, api_key: str, secret_key: str): self.api_key = api_key
    def fetch_ohlcv(self, symbol: str, timeframe: str = "1h", **kwargs):
        params = {"symbol": symbol, "interval": self.interval_map.get(timeframe, "1h")}
        headers = {'X-MEXC-APIKEY': self.api_key}
        data = SafeRequest.get(f"{self.BASE_URL}/api/v3/klines", params=params, headers=headers)
        if not data: return pd.DataFrame()
        df = pd.DataFrame(data, columns=['timestamp','open','high','low','close','volume','close_time','quote_asset_volume','number_of_trades','taker_buy_base_asset_volume','taker_buy_quote_asset_volume'])
        df = df.astype({'open': float, 'high': float, 'low': float, 'close': float, 'volume': float})
        return standardize_df(df)
# (بقیه کلاس‌های Fetcher در اینجا قرار می‌گیرند)

class MultiExchangeFetcher:
    def __init__(self, source: str):
        self.source = source.lower()
        # خواندن کلیدها از متغیرهای محیطی که در Railway تنظیم کردیم
        mexc_api_key = os.getenv('MEXC_API_KEY')
        mexc_secret = os.getenv('MEXC_SECRET_KEY')

        if self.source == "coingecko": self.fetcher = CoingeckoFetcher()
        elif self.source == "kucoin": self.fetcher = KucoinFetcher()
        elif self.source == "mexc":
            if not mexc_api_key or not mexc_secret: raise ValueError("MEXC API keys not set in environment.")
            self.fetcher = MexcFetcher(mexc_api_key, mexc_secret)
        # ... (بقیه elif ها برای gate.io, okx, bitfinex) ...
        else: raise ValueError(f"Unknown exchange source: {self.source}")

    def fetch_ohlcv(self, **kwargs):
        return self.fetcher.fetch_ohlcv(**kwargs)


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
            fetcher = MultiExchangeFetcher(task['source'])
            # ساخت kwargs بر اساس نوع صرافی
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
