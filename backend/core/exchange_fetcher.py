import requests
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(level=logging.INFO)

# ساخت یک session برای استفاده مجدد از اتصالات و افزایش سرعت
session = requests.Session()

class ExchangeFetcher:
    def __init__(self):
        # آدرس‌های پایه برای هر صرافی
        self.base_urls = {
            "mexc": "https://api.mexc.com",
            "kucoin": "https://api.kucoin.com",
            "gateio": "https://api.gate.io",
            "okx": "https://www.okx.com",
        }

    def _safe_request(self, url, params=None, timeout=10):
        """یک متد امن برای ارسال درخواست‌ها"""
        try:
            response = session.get(url, params=params, timeout=timeout)
            response.raise_for_status()  # اگر کد وضعیت خطا بود، exception ایجاد می‌کند
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.warning(f"Failed to fetch {url}: {e}")
            return None

    # --- متدهای دریافت قیمت لحظه‌ای (Ticker) ---

    def get_kucoin_ticker(self, symbol='BTC-USDT'):
        url = f"{self.base_urls['kucoin']}/api/v1/market/stats?symbol={symbol}"
        data = self._safe_request(url)
        if data and data.get('data'):
            ticker = data['data']
            return {
                'symbol': symbol,
                'price': float(ticker.get('last', 0)),
                'change_24h': float(ticker.get('changeRate', 0)) * 100
            }
        return None

    def get_mexc_ticker(self, symbol='BTCUSDT'):
        url = f"{self.base_urls['mexc']}/api/v3/ticker/24hr?symbol={symbol}"
        data = self._safe_request(url)
        if data:
            return {
                'symbol': symbol,
                'price': float(data.get('lastPrice', 0)),
                'change_24h': float(data.get('priceChangePercent', 0)) * 100
            }
        return None

    def get_gateio_ticker(self, symbol='BTC_USDT'):
        # متاسفانه Gate.io دیگر خطای SSL می‌دهد که از سمت سرور آنهاست.
        # فعلا این متد را غیرفعال نگه می‌داریم.
        logging.warning("Gate.io fetcher is currently disabled due to persistent SSL errors.")
        return None

    def get_okx_ticker(self, symbol='BTC-USDT'):
        url = f"{self.base_urls['okx']}/api/v5/market/ticker?instId={symbol}"
        data = self._safe_request(url)
        if data and data.get('data'):
            ticker = data['data'][0]
            return {
                'symbol': symbol,
                'price': float(ticker.get('last', 0)),
                'change_24h': float(ticker.get('chg24h', 0))
            }
        return None
        
    def fetch_all_tickers_concurrently(self, sources, symbol_map):
        """دریافت همزمان قیمت از چندین صرافی برای افزایش سرعت"""
        all_data = {coin: {} for coin in symbol_map.keys()}
        
        # لیست توابع برای فراخوانی
        fetch_functions = {
            'kucoin': self.get_kucoin_ticker,
            'mexc': self.get_mexc_ticker,
            'gateio': self.get_gateio_ticker,
            'okx': self.get_okx_ticker,
        }

        with ThreadPoolExecutor(max_workers=len(sources)) as executor:
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

