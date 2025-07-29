# core/exchange_fetcher.py (نسخه 2.5 با اصلاح نهایی درصد MEXC)

import asyncio
import os
import time
import logging
from typing import Dict, List, Optional, Tuple, Any
import httpx
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(funcName)s] - %(message)s')

EXCHANGE_CONFIG = {
    'mexc': {'base_url': 'https://api.mexc.com', 'kline_endpoint': '/api/v3/klines', 'ticker_endpoint': '/api/v3/ticker/24hr', 'symbol_template': '{base}{quote}', 'timeframe_map': {'5m': '5m', '10m': '10m', '15m': '15m', '1h': '1h', '4h': '4h', '1d': '1d'}, 'rate_limit_delay': 1.0},
    'kucoin': {'base_url': 'https://api.kucoin.com', 'kline_endpoint': '/api/v1/market/candles', 'ticker_endpoint': '/api/v1/market/stats', 'symbol_template': '{base}-{quote}', 'timeframe_map': {'5m': '5min', '10m': '15min', '15m': '15min', '1h': '1hour', '4h': '4hour', '1d': '1day'}, 'rate_limit_delay': 1.0},
    'okx': {'base_url': 'https://www.okx.com', 'kline_endpoint': '/api/v5/market/candles', 'ticker_endpoint': '/api/v5/market/ticker', 'symbol_template': '{base}-{quote}', 'timeframe_map': {'5m': '5m', '10m': '15min', '15m': '15min', '1h': '1H', '4h': '4H', '1d': '1D'}, 'rate_limit_delay': 1.0},
}
SYMBOL_MAP = {'BTC': {'base': 'BTC', 'quote': 'USDT'}, 'ETH': {'base': 'ETH', 'quote': 'USDT'}, 'XRP': {'base': 'XRP', 'quote': 'USDT'}, 'SOL': {'base': 'SOL', 'quote': 'USDT'}, 'DOGE': {'base': 'DOGE', 'quote': 'USDT'}}

class ExchangeFetcher:
    def __init__(self, cache_ttl: int = 60):
        headers = {'User-Agent': 'AiSignalPro/2.5.0', 'Accept': 'application/json'}
        self.client = httpx.AsyncClient(headers=headers, timeout=20, follow_redirects=True)
        self.cache = {}
        self.cache_ttl = cache_ttl
        logging.info("ExchangeFetcher (Legendary Edition v2.5) initialized.")

    def _get_cache_key(self, prefix: str, exchange: str, symbol: str, timeframe: Optional[str] = None) -> str:
        key = f"{prefix}:{exchange}:{symbol}";
        if timeframe: key += f":{timeframe}";
        return key

    def _format_symbol(self, s: str, e: str) -> Optional[str]:
        if s not in SYMBOL_MAP: return None
        c = EXCHANGE_CONFIG.get(e);
        if not c: return None
        return c['symbol_template'].format(base=SYMBOL_MAP[s]['base'], quote=SYMBOL_MAP[s]['quote']).upper()

    def _format_timeframe(self, t: str, e: str) -> Optional[str]:
        c = EXCHANGE_CONFIG.get(e);
        if not c or 'timeframe_map' not in c: return None
        if t == '10m' and '10m' not in c['timeframe_map']:
            logging.warning(f"Timeframe '10m' not supported on {e}, using '15m' instead.");
            return c['timeframe_map'].get('15m')
        return c['timeframe_map'].get(t)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=6), retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)), reraise=False)
    async def _safe_async_request(self, method: str, url: str, **kwargs) -> Optional[Any]:
        exchange_name = kwargs.pop('exchange_name', 'mexc');
        await asyncio.sleep(EXCHANGE_CONFIG.get(exchange_name, {}).get('rate_limit_delay', 1.0));
        response = await self.client.request(method, url, **kwargs);
        response.raise_for_status();
        return response.json()

    def _normalize_kline_data(self, data: List[list], source: str) -> List[Dict[str, Any]]:
        if not data: return []
        try:
            if source == 'okx': data.reverse()
            return [{"timestamp": int(k[0]), "open": float(k[1]), "high": float(k[2]), "low": float(k[3]), "close": float(k[4]), "volume": float(k[5])} for k in data]
        except (ValueError, IndexError): return []

    async def get_klines_from_one_exchange(self, exchange: str, symbol: str, timeframe: str, limit: int = 200) -> Optional[List[Dict]]:
        # ... (این تابع بدون تغییر باقی می‌ماند) ...
        pass
        
    async def get_first_successful_klines(self, symbol: str, timeframe:str) -> Optional[Tuple[pd.DataFrame, str]]:
        # ... (این تابع بدون تغییر باقی می‌ماند) ...
        pass
        
    async def get_ticker_from_one_exchange(self, exchange: str, symbol: str) -> Optional[Dict]:
        cache_key = self._get_cache_key("ticker", exchange, symbol)
        if cache_key in self.cache and (time.time() - self.cache[cache_key]['timestamp']) < 15:
            return self.cache[cache_key]['data']

        config = EXCHANGE_CONFIG.get(exchange)
        formatted_symbol = self._format_symbol(symbol, exchange)
        if not all([config, formatted_symbol, 'ticker_endpoint' in config]):
            return None

        url = config['base_url'] + config['ticker_endpoint']
        params = {'instId': formatted_symbol} if exchange == 'okx' else {'symbol': formatted_symbol}
        
        raw_data = await self._safe_async_request('GET', url, params=params, exchange_name=exchange)
        if raw_data:
            price, change = 0.0, 0.0
            try:
                if exchange == 'mexc':
                    data = raw_data[0] if isinstance(raw_data, list) and raw_data else raw_data
                    price = float(data.get('lastPrice', 0))
                    # --- اصلاح شد: درصد MEXC باید در 100 ضرب شود ---
                    change = float(data.get('priceChangePercent', 0)) * 100
                elif exchange == 'kucoin' and raw_data.get('data'):
                    data = raw_data['data']
                    price = float(data.get('last', 0))
                    change = float(data.get('changeRate', 0)) * 100
                elif exchange == 'okx' and raw_data.get('data'):
                    data = raw_data['data'][0]
                    price = float(data.get('last', 0))
                    change = float(data.get('chg24h', 0)) * 100

                if price > 0:
                    result = {'price': price, 'change_24h': change, 'source': exchange, 'symbol': symbol}
                    logging.info(f"✅ Final Ticker Data: {result}")
                    self.cache[cache_key] = {'timestamp': time.time(), 'data': result}
                    return result
                else:
                    logging.warning(f"Price returned as 0 for {exchange} on {symbol}. Trying next exchange.")
                    return None

            except (ValueError, TypeError, IndexError, KeyError) as e:
                 logging.warning(f"Ticker data normalization failed for {exchange} on {symbol}: {e}")

        logging.warning(f"Final attempt failed for ticker from {exchange} on {symbol}.")
        return None

    async def get_first_successful_ticker(self, symbol: str) -> Optional[Dict]:
        tasks = [asyncio.create_task(self.get_ticker_from_one_exchange(ex, symbol), name=ex) for ex in ['kucoin', 'okx', 'mexc']]
        for task in asyncio.as_completed(tasks):
            try:
                result = await task;
                if result: return result
            except Exception: continue
        logging.error(f"Critical Failure: Could not fetch ticker for {symbol} from any exchange.");
        return None

    async def close(self):
        await self.client.aclose()
