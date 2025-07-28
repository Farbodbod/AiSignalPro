# core/exchange_fetcher.py (نسخه افسانه‌ای و بی‌نقص)
# Author: Ai Signal Pro & Gemini
# Features: Async, Multi-Exchange, Fallback, Normalization, Caching, Retry (Tenacity)

import asyncio
import os
import time
import logging
from typing import Dict, List, Optional, Tuple, Any
import httpx
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# --- تنظیمات لاگ‌گیری ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(funcName)s] - %(message)s')

# ۱. پیکربندی مرکزی و هوشمند
EXCHANGE_CONFIG = {
    'mexc': {
        'base_url': 'https://api.mexc.com',
        'kline_endpoint': '/api/v3/klines',
        'symbol_template': '{base}{quote}',
        'timeframe_map': {'5m': '5m', '10m': '10m', '15m': '15m', '1h': '1h', '4h': '4h', '1d': '1d'},
        'rate_limit_delay': 1.0,
    },
    'kucoin': {
        'base_url': 'https://api.kucoin.com',
        'kline_endpoint': '/api/v1/market/candles',
        'symbol_template': '{base}-{quote}',
        'timeframe_map': {'5m': '5min', '10m': '15min', '15m': '15min', '1h': '1hour', '4h': '4hour', '1d': '1day'},
        'rate_limit_delay': 1.0,
    },
    'okx': {
        'base_url': 'https://www.okx.com',
        'kline_endpoint': '/api/v5/market/candles',
        'symbol_template': '{base}-{quote}',
        'timeframe_map': {'5m': '5m', '10m': '15m', '15m': '15m', '1h': '1H', '4h': '4H', '1d': '1D'},
        'rate_limit_delay': 1.0,
    }
}

# ۲. مدیریت نمادها
SYMBOL_MAP = {
    'BTC': {'base': 'BTC', 'quote': 'USDT'},
    'ETH': {'base': 'ETH', 'quote': 'USDT'},
    'XRP': {'base': 'XRP', 'quote': 'USDT'},
    'SOL': {'base': 'SOL', 'quote': 'USDT'},
    'DOGE': {'base': 'DOGE', 'quote': 'USDT'},
}

# ۳. کلاس اصلی و پیشرفته
class ExchangeFetcher:
    """
    نسخه افسانه‌ای Fetcher: غیرهمزمان، مقاوم در برابر خطا با قابلیت تلاش مجدد،
    کش هوشمند، و نرمال‌سازی دقیق داده‌ها.
    """
    def __init__(self, cache_ttl: int = 60):
        headers = {'User-Agent': 'AiSignalPro/1.2.0', 'Accept': 'application/json'}
        self.client = httpx.AsyncClient(headers=headers, timeout=20, follow_redirects=True)
        self.cache = {}
        self.cache_ttl = cache_ttl
        logging.info("ExchangeFetcher (Legendary Edition) initialized.")

    def _get_cache_key(self, exchange: str, symbol: str, timeframe: str) -> str:
        return f"{exchange}:{symbol}:{timeframe}"

    def _format_symbol(self, standard_symbol: str, exchange: str) -> Optional[str]:
        if standard_symbol not in SYMBOL_MAP: return None
        config = EXCHANGE_CONFIG.get(exchange)
        if not config: return None
        return config['symbol_template'].format(base=SYMBOL_MAP[standard_symbol]['base'], quote=SYMBOL_MAP[standard_symbol]['quote'])

    def _format_timeframe(self, standard_timeframe: str, exchange: str) -> Optional[str]:
        config = EXCHANGE_CONFIG.get(exchange)
        if not config or 'timeframe_map' not in config: return None
        
        # بهبود یافته: لاگ کردن جایگزینی تایم‌فریم
        if standard_timeframe == '10m' and '10m' not in config['timeframe_map']:
            logging.warning(f"Timeframe '10m' not supported on {exchange}, using '15m' instead.")
            return config['timeframe_map'].get('15m')
        
        return config['timeframe_map'].get(standard_timeframe)

    # بهبود یافته: تلاش مجدد هوشمند با Tenacity
    @retry(
        stop=stop_after_attempt(3), 
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        reraise=True # اگر بعد از ۳ بار تلاش همچنان خطا داشت، آن را نمایش بده
    )
    async def _safe_async_request(self, method: str, url: str, **kwargs) -> Optional[Any]:
        # بهبود یافته: تأخیر برای Rate Limit قبل از هر تلاش
        await asyncio.sleep(EXCHANGE_CONFIG.get(kwargs.get('exchange_name', 'mexc'), {}).get('rate_limit_delay', 1.0))
        response = await self.client.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()

    def _normalize_kline_data(self, data: List[list], source: str) -> List[Dict[str, Any]]:
        """
        (بسیار مهم) خروجی تمام صرافی‌ها را به یک فرمت استاندارد و یکسان تبدیل می‌کند.
        """
        if not data: return []
        
        normalized_data = []
        try:
            if source == 'okx':
                # OKX داده‌ها را معکوس (از جدید به قدیم) می‌دهد و فرمت متفاوتی دارد
                data.reverse() 
            
            for k in data:
                normalized_data.append({
                    "timestamp": int(k[0]),
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5])
                })
            return normalized_data
        except (ValueError, IndexError) as e:
            logging.error(f"Data normalization failed for {source}: {e} | Raw data sample: {data[0] if data else 'Empty'}")
            return []


    async def get_klines_from_one_exchange(self, exchange: str, symbol: str, timeframe: str, limit: int = 200) -> Optional[List[Dict]]:
        # بهبود یافته: چک کردن کش قبل از ارسال درخواست
        cache_key = self._get_cache_key(exchange, symbol, timeframe)
        if cache_key in self.cache and (time.time() - self.cache[cache_key]['timestamp']) < self.cache_ttl:
            logging.info(f"CACHE HIT: Returning cached data for {cache_key}")
            return self.cache[cache_key]['data']
        
        config = EXCHANGE_CONFIG.get(exchange)
        formatted_symbol = self._format_symbol(symbol, exchange)
        formatted_timeframe = self._format_timeframe(timeframe, exchange)
        if not all([config, formatted_symbol, formatted_timeframe, 'kline_endpoint' in config]): return None
        
        url = config['base_url'] + config['kline_endpoint']
        params = {}
        if exchange == 'okx': params = {'instId': formatted_symbol, 'bar': formatted_timeframe, 'limit': str(limit)}
        else: params = {'symbol': formatted_symbol, 'interval': formatted_timeframe, 'limit': str(limit)}
        if exchange == 'kucoin': params['type'] = params.pop('interval')
        
        try:
            raw_data = await self._safe_async_request('GET', url, params=params, exchange_name=exchange)
            if raw_data:
                kline_list = raw_data.get('data') if isinstance(raw_data, dict) and 'data' in raw_data else raw_data
                if isinstance(kline_list, list):
                    normalized_data = self._normalize_kline_data(kline_list, exchange)
                    if normalized_data:
                        # بهبود یافته: ذخیره نتیجه موفق در کش
                        self.cache[cache_key] = {'timestamp': time.time(), 'data': normalized_data}
                        return normalized_data
        except Exception as e:
            # بهبود یافته: لاگ کردن دقیق خطا برای هر صرافی
            logging.warning(f"Failed to fetch or process data from {exchange} for {symbol}@{timeframe}. Reason: {e}")

        return None
        
    async def get_first_successful_klines(self, symbol: str, timeframe:str) -> Optional[Tuple[pd.DataFrame, str]]:
        exchanges = ['mexc', 'kucoin', 'okx']
        
        # بهبود یافته: الگوی امن‌تر برای مدیریت تسک‌های موازی
        tasks = [asyncio.create_task(self.get_klines_from_one_exchange(ex, symbol, timeframe), name=ex) for ex in exchanges]
        for task in asyncio.as_completed(tasks):
            source_exchange = task.get_name()
            result = await task
            if result:
                logging.info(f"Data acquired from '{source_exchange}' for {symbol}@{timeframe}.")
                return pd.DataFrame(result), source_exchange
        
        logging.error(f"Critical Failure: Could not fetch klines for {symbol}@{timeframe} from any available exchange.")
        return None, None
        
    async def close(self):
        await self.client.aclose()
