import requests
import time
import logging
import hmac
import hashlib
import base64
import json
from urllib.parse import urlencode
from datetime import datetime

logging.basicConfig(level=logging.INFO)

class ExchangeFetcher:
    def __init__(self):
        self.exchanges = {
            "MEXC": {
                "api_key": "mx0vglCzPWJOKxnF26",
                "secret": "ee6b2172fce94576a7795fd0c098ebab",
                "base_url": "https://api.mexc.com",
                "fetch_func": self.fetch_mexc
            },
            "KuCoin": {
                "api_key": "",  # Add if available
                "secret": "",
                "passphrase": "",
                "base_url": "https://api.kucoin.com",
                "fetch_func": self.fetch_kucoin
            },
            "GateIO": {
                "base_url": "https://api.gate.io",
                "fetch_func": self.fetch_gateio
            },
            "OKX": {
                "base_url": "https://www.okx.com",
                "fetch_func": self.fetch_okx
            },
            "Toobit": {
                "base_url": "https://api.toobit.com",
                "fetch_func": self.fetch_toobit
            }
        }

    def safe_request(self, url, headers=None, params=None, retries=3, delay=2):
        for attempt in range(retries):
            try:
                response = requests.get(url, headers=headers, params=params, timeout=10)
                if response.status_code == 200:
                    return response.json()
                else:
                    logging.warning(f"Non-200 response {response.status_code} from {url}")
            except requests.exceptions.SSLError:
                logging.error(f"SSL Error from {url}")
            except requests.exceptions.RequestException as e:
                logging.error(f"Request Exception: {str(e)}")
            time.sleep(delay)
        return None

    def fetch_mexc(self, symbol="BTC_USDT", interval="1m", limit=100):
        url = f"{self.exchanges['MEXC']['base_url']}/api/v3/klines"
        params = {"symbol": symbol.replace("_", ""), "interval": interval, "limit": limit}
        data = self.safe_request(url, params=params)
        if data:
            return [{"timestamp": int(k[0]), "open": float(k[1]), "high": float(k[2]),
                     "low": float(k[3]), "close": float(k[4]), "volume": float(k[5])}
                    for k in data]
        return []

    def fetch_kucoin(self, symbol="BTC-USDT", interval="1min", limit=100):
        url = f"{self.exchanges['KuCoin']['base_url']}/api/v1/market/candles"
        params = {"symbol": symbol, "type": interval}
        data = self.safe_request(url, params=params)
        if data and data.get("data"):
            return [{"timestamp": int(datetime.strptime(k[0], "%Y-%m-%dT%H:%M:%S.%fZ").timestamp()*1000),
                     "open": float(k[1]), "close": float(k[2]),
                     "high": float(k[3]), "low": float(k[4]), "volume": float(k[5])}
                    for k in data["data"][:limit]]
        return []

    def fetch_gateio(self, symbol="BTC_USDT", interval="1m", limit=100):
        url = f"{self.exchanges['GateIO']['base_url']}/api/v4/spot/candlesticks"
        params = {"currency_pair": symbol, "interval": interval, "limit": limit}
        data = self.safe_request(url, params=params)
        if data:
            return [{"timestamp": int(float(k[0])*1000), "volume": float(k[1]), "close": float(k[2]),
                     "high": float(k[3]), "low": float(k[4]), "open": float(k[5])}
                    for k in data]
        return []

    def fetch_okx(self, symbol="BTC-USDT", interval="1m", limit=100):
        url = f"{self.exchanges['OKX']['base_url']}/api/v5/market/candles"
        params = {"instId": symbol, "bar": interval, "limit": str(limit)}
        data = self.safe_request(url, params=params)
        if data and "data" in data:
            return [{"timestamp": int(datetime.strptime(k[0], "%Y-%m-%dT%H:%M:%S.%fZ").timestamp()*1000),
                     "open": float(k[1]), "high": float(k[2]), "low": float(k[3]),
                     "close": float(k[4]), "volume": float(k[5])}
                    for k in data["data"]]
        return []

    def fetch_toobit(self, symbol="BTC_USDT", interval="1min", limit=100):
        url = f"{self.exchanges['Toobit']['base_url']}/quote/v1/klines"
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        data = self.safe_request(url, params=params)
        if data and data.get("data"):
            return [{"timestamp": int(k["id"])*1000, "open": float(k["open"]),
                     "high": float(k["high"]), "low": float(k["low"]),
                     "close": float(k["close"]), "volume": float(k["vol"])}
                    for k in data["data"]]
        return []

    def fetch_all(self, symbol="BTC_USDT", interval="1m", limit=100):
        all_data = {}
        for name, ex in self.exchanges.items():
            try:
                logging.info(f"Fetching data from {name}...")
                data = ex["fetch_func"](symbol, interval, limit)
                all_data[name] = data
            except Exception as e:
                logging.error(f"Error in {name}: {e}")
        return all_data


# === اجرای مستقیم برای تست ===
if __name__ == "__main__":
    fetcher = ExchangeFetcher()
    result = fetcher.fetch_all("BTC_USDT", "1m", 50)
    for ex, candles in result.items():
        print(f"{ex} | تعداد کندل‌ها: {len(candles)}")
        if candles:
            print("نمونه:", candles[0])
