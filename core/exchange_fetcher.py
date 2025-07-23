"""
multi_exchange_fetcher_v4.py
Parallel Multi-Coin & Multi-Exchange OHLCV Fetcher
"""

import requests
import pandas as pd
import time
import os
from datetime import datetime
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

# ... (کلاس SafeRequest و تابع standardize_df بدون تغییر) ...
class SafeRequest:
    # ...
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
    if df is None or df.empty: return pd.DataFrame()
    # ... (بقیه کد) ...
    df = df.dropna()
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.sort_values('timestamp')
    df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
    df.set_index('timestamp', inplace=True)
    return df


# ... (تمام کلاس‌های Fetcher برای هر صرافی بدون تغییر باقی می‌مانند) ...
class KucoinFetcher:
    # ...
    BASE_URL = "https://api.kucoin.com"
    interval_map = {"1m": "1min", "5m": "5min", "15m": "15min", "1h": "1hour", "4h": "4hour", "1d": "1day"}
    def fetch_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 300, **kwargs):
        interval = self.interval_map.get(timeframe, "1hour")
        url = f"{self.BASE_URL}/api/v1/market/candles"
        params = {"symbol": symbol, "type": interval}
        data = SafeRequest.get(url, params=params)
        if not data or 'data' not in data: return pd.DataFrame()
        df = pd.DataFrame(data['data'], columns=['timestamp', 'open', 'close', 'high', 'low', 'volume', 'turnover'])
        df['timestamp'] = df['timestamp'].astype(float) * 1000
        df = df.astype({'open': float, 'high': float, 'low': float, 'close': float, 'volume': float})
        return standardize_df(df)

# (کلاس‌های دیگر مانند GateioFetcher, OkxFetcher و... در اینجا قرار می‌گیرند)

class MultiExchangeFetcher:
    # ... (کد قبلی این کلاس بدون تغییر) ...
    def __init__(self, source: str):
        self.source = source.lower()
        if self.source == "kucoin": self.fetcher = KucoinFetcher()
        elif self.source == "gate.io": self.fetcher = GateioFetcher()
        # ... (بقیه elif ها) ...
        else: raise ValueError(f"Unknown exchange source: {self.source}")

    def fetch_ohlcv(self, **kwargs):
        return self.fetcher.fetch_ohlcv(**kwargs)


# ===================================================================
# تابع جدید برای دریافت همزمان دیتا برای چندین ارز
# ===================================================================
def fetch_all_coins_concurrently(sources: List[str], symbol_map: Dict[str, Dict[str, str]], timeframe: str) -> Dict[str, Dict[str, pd.DataFrame]]:
    """
    از چندین صرافی برای چندین ارز به صورت موازی دیتا دریافت می‌کند.
    :param sources: لیستی از نام صرافی‌ها. e.g., ['kucoin', 'gate.io']
    :param symbol_map: دیکشنری تو در تو برای نگاشت نمادها. 
                      e.g., {'BTC': {'kucoin': 'BTC-USDT', 'gate.io': 'BTC_USDT'}, ...}
    :param timeframe: تایم فریم مورد نظر. e.g., '1h'
    :return: دیکشنری تو در تو حاوی دیتافریم‌ها. e.g., {'BTC': {'kucoin': df, 'gate.io': df}, ...}
    """
    results = {}
    tasks = []

    # ایجاد لیست وظایف
    for coin, mapping in symbol_map.items():
        results[coin] = {}
        for source in sources:
            if source in mapping:
                symbol = mapping[source]
                tasks.append({'coin': coin, 'source': source, 'symbol': symbol, 'timeframe': timeframe})

    def _fetch_one(task):
        """تابع داخلی برای اجرا در هر ترد"""
        try:
            fetcher = MultiExchangeFetcher(task['source'])
            df = fetcher.fetch_ohlcv(symbol=task['symbol'], timeframe=task['timeframe'])
            return task['coin'], task['source'], df
        except Exception as e:
            print(f"Failed to fetch {task['symbol']} from {task['source']}: {e}")
            return task['coin'], task['source'], pd.DataFrame()

    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        future_to_task = {executor.submit(_fetch_one, task): task for task in tasks}
        
        for future in as_completed(future_to_task):
            coin, source, df = future.result()
            if not df.empty:
                results[coin][source] = df
    
    return results

