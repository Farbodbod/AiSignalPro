# تمام محتوای فایل core/exchange_fetcher.py را با این کد جایگزین کنید
import requests
import pandas as pd
import time
import os
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

class SafeRequest:
    @staticmethod
    def get(url, params=None, headers=None, retries=3, timeout=10):
        # هدر User-Agent را برای شبیه‌سازی مرورگر اضافه می‌کنیم
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
            except Exception as e:
                print(f"Error in SafeRequest: {e}")
                time.sleep(1)
        return None

# ... (بقیه کلاس‌ها و توابع این فایل بدون تغییر باقی می‌مانند) ...
def standardize_df(df): #...
    if df is None or df.empty: return pd.DataFrame()
    df = df.dropna()
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.sort_values('timestamp')
    df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
    df.set_index('timestamp', inplace=True)
    return df
class CoingeckoFetcher: #...
    BASE_URL = "https://api.coingecko.com/api/v3"
    def fetch_ohlcv(self, coin_id: str, timeframe: str = "1h", **kwargs):
        params = {"vs_currency": "usd", "days": "1"}
        url = f"{self.BASE_URL}/coins/{coin_id}/market_chart"
        data = SafeRequest.get(url, params=params)
        if not data or 'prices' not in data: raise ValueError("Invalid response from Coingecko.")
        prices = pd.DataFrame(data['prices'], columns=['timestamp', 'close'])
        volumes = pd.DataFrame(data['total_volumes'], columns=['timestamp', 'volume'])
        df = prices.merge(volumes, on='timestamp')
        for col in ['open', 'high', 'low']: df[col] = df['close']
        return standardize_df(df)
# (کلاس‌های دیگر fetcher مانند Kucoin, Gate.io و ... در اینجا قرار می‌گیرند)
# ...
def fetch_all_coins_concurrently(sources: List[str], symbol_map: Dict[str, Dict[str, str]], timeframe: str) -> Dict[str, Dict[str, pd.DataFrame]]:
    # ... (کد این تابع بدون تغییر است)
    results = {}; tasks = []
    for coin, mapping in symbol_map.items():
        results[coin] = {}
        for source in sources:
            if source in mapping:
                tasks.append({'coin': coin, 'source': source, 'symbol': mapping[source], 'timeframe': timeframe})
    def _fetch_one(task):
        try:
            fetcher = MultiExchangeFetcher(task['source']).get_fetcher()
            kwargs = {'timeframe': task['timeframe']}
            if task['source'] == 'coingecko': kwargs['coin_id'] = task['symbol']
            else: kwargs['symbol'] = task['symbol']
            df = fetcher.fetch_ohlcv(**kwargs)
            return task['coin'], task['source'], df
        except Exception as e:
            return task['coin'], task['source'], pd.DataFrame()
    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        future_to_task = {executor.submit(_fetch_one, task): task for task in tasks}
        for future in as_completed(future_to_task):
            coin, source, df = future.result()
            if not df.empty: results[coin][source] = df
    return results
