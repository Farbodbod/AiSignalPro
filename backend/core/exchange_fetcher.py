# core/exchange_fetcher.py (v5.4 - Final)

import asyncio
import time
import logging
from typing import Dict, List, Optional, Tuple, Any
import httpx
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

EXCHANGE_CONFIG = {
    'mexc': {'base_url': 'https://api.mexc.com', 'kline_endpoint': '/api/v3/klines', 'max_limit_per_req': 400, 'symbol_template': '{base}{quote}', 'timeframe_map': {'5m': '5m', '15m': '15m', '1h': '1h', '4h': '4h', '1d': '1d'}, 'rate_limit_delay': 0.5},
    'kucoin': {'base_url': 'https://api.kucoin.com', 'kline_endpoint': '/api/v1/market/candles', 'max_limit_per_req': 400, 'symbol_template': '{base}-{quote}', 'timeframe_map': {'5m': '5min', '15m': '15min', '1h': '1hour', '4h': '4hour', '1d': '1day'}, 'rate_limit_delay': 0.5},
    'okx': {'base_url': 'https://www.okx.com', 'kline_endpoint': '/api/v5/market/candles', 'max_limit_per_req': 400, 'symbol_template': '{base}-{quote}', 'timeframe_map': {'5m': '5m', '15m': '15m', '1h': '1H', '4h': '4H', '1d': '1D'}, 'rate_limit_delay': 0.2},
}
SYMBOL_MAP = {'BTC/USDT': {'base': 'BTC', 'quote': 'USDT'}, 'ETH/USDT': {'base': 'ETH', 'quote': 'USDT'}}

class ExchangeFetcher:
    def __init__(self, config: Dict[str, Any] = None, cache_ttl: int = 60):
        headers = {'User-Agent': 'AiSignalPro/5.4.0', 'Accept': 'application/json'}
        self.client = httpx.AsyncClient(headers=headers, timeout=20, follow_redirects=True)
        self.cache = {}
        self.cache_ttl = cache_ttl
        
        effective_config = config or {}
        self.exchange_config = effective_config.get("exchange_specific", EXCHANGE_CONFIG)
        self.symbol_map = effective_config.get("symbol_map", SYMBOL_MAP)
        
        logging.info("ExchangeFetcher (Final v5.4) initialized.")

    def _format_symbol(self, s: str, e: str) -> Optional[str]:
        base_symbol, quote_symbol = s.split('/')
        c = self.exchange_config.get(e)
        return c['symbol_template'].format(base=base_symbol, quote=quote_symbol).upper() if c else None

    def _format_timeframe(self, t: str, e: str) -> Optional[str]:
        c = self.exchange_config.get(e)
        return c.get('timeframe_map', {}).get(t) if c else None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=6), reraise=True)
    async def _safe_async_request(self, method: str, url: str, **kwargs) -> Optional[Any]:
        exchange_name = kwargs.pop('exchange_name', 'unknown')
        delay = self.exchange_config.get(exchange_name, {}).get('rate_limit_delay', 1.0)
        await asyncio.sleep(delay)
        response = await self.client.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()

    def _normalize_kline_data(self, data: List[list], source: str) -> List[Dict[str, Any]]:
        if not data: return []
        normalized_data = []
        if source == 'okx': data.reverse()
        for k in data:
            try:
                candle = {"timestamp": int(k[0]), "open": float(k[1]), "high": float(k[2]), "low": float(k[3]), "close": float(k[4]), "volume": float(k[5])}
                normalized_data.append(candle)
            except (ValueError, TypeError, IndexError):
                logger.warning(f"Skipping malformed candle from {source}: {k}")
        return normalized_data

    async def get_klines_from_one_exchange(self, exchange: str, symbol: str, timeframe: str, limit: int = 500) -> Optional[List[Dict]]:
        config = self.exchange_config.get(exchange)
        formatted_symbol = self._format_symbol(symbol, exchange)
        formatted_timeframe = self._format_timeframe(timeframe, exchange)

        if not all([config, formatted_symbol, formatted_timeframe]): return None
        
        all_normalized_data = []
        remaining_limit = limit
        end_timestamp = None
        max_per_req = config.get('max_limit_per_req', 1000)
        page_num = 1

        while remaining_limit > 0:
            fetch_limit = min(remaining_limit, max_per_req)
            if fetch_limit <= 0: break
            
            logger.info(f"Fetching page #{page_num} for {symbol}@{timeframe} from {exchange} (limit: {fetch_limit})...")
            
            url = config['base_url'] + config['kline_endpoint']
            params = {'limit': str(fetch_limit)}

            if exchange == 'okx':
                params.update({'instId': formatted_symbol, 'bar': formatted_timeframe})
                if end_timestamp: params['before'] = str(end_timestamp)
            elif exchange == 'kucoin':
                params.update({'symbol': formatted_symbol, 'type': formatted_timeframe})
                if end_timestamp: params['endAt'] = int(end_timestamp / 1000)
            else:
                params.update({'symbol': formatted_symbol, 'interval': formatted_timeframe})
                if end_timestamp: params['endTime'] = end_timestamp
            
            try:
                raw_data = await self._safe_async_request('GET', config['base_url'] + config['kline_endpoint'], params=params, exchange_name=exchange)
                kline_list = raw_data.get('data') if isinstance(raw_data, dict) and 'data' in raw_data else raw_data
                
                if isinstance(kline_list, list) and kline_list:
                    normalized_data = self._normalize_kline_data(kline_list, exchange)
                    all_normalized_data = normalized_data + all_normalized_data
                    end_timestamp = normalized_data[0]['timestamp'] - 1
                    remaining_limit -= len(normalized_data)
                    page_num += 1
                else:
                    logger.info(f"Exchange returned no more data. Ending pagination.")
                    break
            except Exception as e:
                logger.warning(f"Request failed during pagination: {e}")
                break
        
        if all_normalized_data:
            return all_normalized_data[-limit:]
        
        return None

    async def get_first_successful_klines(self, symbol: str, timeframe: str, limit: int = 200) -> Optional[Tuple[pd.DataFrame, str]]:
        exchanges = list(self.exchange_config.keys())
        
        async def fetch_and_tag(exchange: str):
            result = await self.get_klines_from_one_exchange(exchange, symbol, timeframe, limit=limit)
            if result: 
                df = pd.DataFrame(result)
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('timestamp', inplace=True)
                return exchange, df
            return None

        tasks = [asyncio.create_task(fetch_and_tag(ex)) for ex in exchanges]
        
        try:
            for future in asyncio.as_completed(tasks):
                result_tuple = await future
                if result_tuple:
                    for task in tasks: 
                        if not task.done(): task.cancel()
                    source_exchange, df = result_tuple
                    logger.info(f"Klines acquired from '{source_exchange}' for {symbol}@{timeframe} with {len(df)} rows (requested {limit}).")
                    return df, source_exchange
        except asyncio.CancelledError:
             logging.info(f"Kline fetch tasks for {symbol} cancelled as a successful one was completed.")
        except Exception as e:
            logger.error(f"An unexpected error in get_first_successful_klines: {e}")

        logger.error(f"Critical Failure: Could not fetch klines for {symbol}@{timeframe} from any exchange.")
        return None, None

    async def close(self):
        await self.client.aclose()
