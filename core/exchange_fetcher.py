"""
multi_exchange_fetcher_v3.py

Parallel Multi-Exchange OHLCV Fetcher
قابلیت دریافت همزمان و موازی دیتا از چندین صرافی
"""

import requests
import pandas as pd
import time
import os
from datetime import datetime
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

# ... (کلاس SafeRequest و تابع standardize_df بدون تغییر باقی می‌مانند) ...
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
        return None # در صورت خطا None برمی‌گردانیم

def standardize_df(df):
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.dropna()
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.sort_values('timestamp')
    df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
    df.set_index('timestamp', inplace=True)
    return df

# ... (تمام کلاس‌های Fetcher برای هر صرافی بدون تغییر باقی می‌مانند) ...
class CoingeckoFetcher:
    # ... (کد قبلی) ...
    BASE_URL = "https://api.coingecko.com/api/v3"
    interval_map = {"1h": "hourly", "1d": "daily"}

    def fetch_ohlcv(self, coin_id: str, vs_currency: str = "usd", days: str = "30", timeframe: str = "1h", **kwargs):
        # ... (کد قبلی) ...
        interval = self.interval_map.get(timeframe, "hourly")
        url = f"{self.BASE_URL}/coins/{coin_id}/market_chart"
        params = {"vs_currency": vs_currency, "days": days, "interval": interval}
        data = SafeRequest.get(url, params=params)
        if not data or 'prices' not in data:
            raise ValueError("Invalid response from Coingecko.")
        prices = pd.DataFrame(data['prices'], columns=['timestamp', 'close'])
        volumes = pd.DataFrame(data['total_volumes'], columns=['timestamp', 'volume'])
        df = prices.merge(volumes, on='timestamp')
        for col in ['open', 'high', 'low']:
            df[col] = df['close']
        df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        return standardize_df(df)

class KucoinFetcher:
    # ... (کد قبلی) ...
    BASE_URL = "https://api.kucoin.com"
    interval_map = {"1m": "1min", "5m": "5min", "15m": "15min", "1h": "1hour", "4h": "4hour", "1d": "1day"}
    def fetch_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 300, **kwargs):
        # ... (کد قبلی) ...
        interval = self.interval_map.get(timeframe, "1hour")
        url = f"{self.BASE_URL}/api/v1/market/candles"
        params = {"symbol": symbol, "type": interval, "limit": limit}
        data = SafeRequest.get(url, params=params)
        if not data or 'data' not in data:
            return pd.DataFrame()
        df = pd.DataFrame(data['data'], columns=['timestamp', 'open', 'close', 'high', 'low', 'volume', 'turnover'])
        df['timestamp'] = df['timestamp'].astype(float) * 1000
        df = df.astype({'open': float, 'high': float, 'low': float, 'close': float, 'volume': float})
        return standardize_df(df)

# (کلاس‌های دیگر مانند GateioFetcher, OkxFetcher و... در اینجا قرار می‌گیرند)

class MultiExchangeFetcher:
    # ... (کد قبلی این کلاس بدون تغییر) ...
    def __init__(self, source: str):
        self.source = source.lower()
        mexc_api_key = os.getenv('MEXC_API_KEY')
        mexc_secret = os.getenv('MEXC_SECRET_KEY')
        cmc_api_key = os.getenv('CMC_API_KEY')

        if self.source == "coingecko": self.fetcher = CoingeckoFetcher()
        elif self.source == "kucoin": self.fetcher = KucoinFetcher()
        # ... (بقیه elif ها) ...
        else: raise ValueError(f"Unknown exchange source: {self.source}")

    def fetch_ohlcv(self, **kwargs):
        return self.fetcher.fetch_ohlcv(**kwargs)


# ===================================================================
# تابع جدید برای دریافت همزمان دیتا
# ===================================================================
def fetch_all_sources_concurrently(sources: List[str], symbol_map: Dict[str, str], timeframe: str, limit: int = 100) -> Dict[str, pd.DataFrame]:
    """
    از چندین صرافی به صورت موازی دیتا دریافت می‌کند.
    
    :param sources: لیستی از نام صرافی‌ها. e.g., ['kucoin', 'gate.io']
    :param symbol_map: دیکشنری برای نگاشت نام عمومی به نماد خاص هر صرافی. 
                      e.g., {'kucoin': 'BTC-USDT', 'gate.io': 'BTC_USDT'}
    :param timeframe: تایم فریم مورد نظر. e.g., '1h'
    :param limit: تعداد کندل‌ها.
    :return: دیکشنری حاوی دیتافریم هر صرافی.
    """
    results = {}

    def _fetch_one(source: str):
        """یک تابع داخلی برای اجرا در هر ترد"""
        try:
            fetcher = MultiExchangeFetcher(source)
            symbol = symbol_map.get(source)
            if not symbol:
                print(f"No symbol provided for {source}, skipping.")
                return source, pd.DataFrame()
            
            # پارامترهای خاص هر صرافی را جدا می‌کنیم
            kwargs = {'symbol': symbol, 'timeframe': timeframe, 'limit': limit}
            if source == 'coingecko':
                kwargs = {'coin_id': symbol, 'timeframe': timeframe, 'days': '7'} # مثال برای پارامتر متفاوت
                
            df = fetcher.fetch_ohlcv(**kwargs)
            return source, df
        except Exception as e:
            print(f"Failed to fetch from {source}: {e}")
            return source, pd.DataFrame()

    with ThreadPoolExecutor(max_workers=len(sources)) as executor:
        # ارسال تمام وظایف به ترد پول
        future_to_source = {executor.submit(_fetch_one, source): source for source in sources}
        
        # جمع‌آوری نتایج به محض آماده شدن
        for future in as_completed(future_to_source):
            source, df = future.result()
            if not df.empty:
                results[source] = df

    return results

# مثال تست:
if __name__ == "__main__":
    # لیستی از صرافی‌هایی که می‌خواهیم از آنها دیتا بگیریم
    target_sources = ['kucoin', 'gate.io'] # می‌توانید صرافی‌های دیگر را هم اضافه کنید
    
    # نگاشت نماد بیت‌کوین برای هر صرافی
    btc_symbols = {
        'kucoin': 'BTC-USDT',
        'gate.io': 'BTC_USDT',
        'okx': 'BTC-USDT',
        'bitfinex': 'BTCUSD'
    }

    print("Fetching data concurrently...")
    all_data = fetch_all_sources_concurrently(target_sources, btc_symbols, '1h')
    
    print("\n--- Results ---")
    for source, dataframe in all_data.items():
        print(f"\nData from: {source}")
        print(dataframe.tail(3))
