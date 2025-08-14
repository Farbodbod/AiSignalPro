# core/exchange_fetcher.py (v5.0 - Decoupled & Hardened Edition)

import asyncio
import time
import logging
from typing import Dict, List, Optional, Tuple, Any
import httpx
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

class ExchangeFetcher:
    """
    The definitive, world-class data fetching engine for AiSignalPro (v5.0).
    This version features:
    1.  Robust, multi-request pagination to bypass exchange API limits.
    2.  Decoupled configuration, making the class modular and testable.
    3.  Enhanced logging for better debugging of the fetching process.
    4.  Asynchronous, multi-exchange failover for maximum reliability.
    """
    def __init__(self, config: Dict[str, Any], cache_ttl: int = 60):
        headers = {'User-Agent': 'AiSignalPro/5.0.0', 'Accept': 'application/json'}
        self.client = httpx.AsyncClient(headers=headers, timeout=20, follow_redirects=True)
        self.cache = {}
        self.cache_ttl = cache_ttl
        
        # --- ✨ UPGRADE: Configuration is now passed in, not hardcoded ---
        self.exchange_config = config.get("exchange_specific", {})
        self.symbol_map = config.get("symbol_map", {})
        
        logging.info("ExchangeFetcher (Decoupled & Hardened Edition v5.0) initialized.")

    def _format_symbol(self, symbol: str, exchange: str) -> Optional[str]:
        base_symbol, quote_symbol = symbol.split('/')
        config = self.exchange_config.get(exchange)
        if not config: return None
        return config['symbol_template'].format(base=base_symbol, quote=quote_symbol).upper()

    def _format_timeframe(self, timeframe: str, exchange: str) -> Optional[str]:
        config = self.exchange_config.get(exchange)
        if not config: return None
        return config.get('timeframe_map', {}).get(timeframe)

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
            logger.info(f"Fetching page #{page_num} for {symbol}@{timeframe} from {exchange} (limit: {fetch_limit})...")
            
            url = config['base_url'] + config['kline_endpoint']
            params = {'limit': fetch_limit}

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
                raw_data = await self._safe_async_request('GET', url, params=params, exchange_name=exchange)
                kline_list = raw_data.get('data') if isinstance(raw_data, dict) and 'data' in raw_data else raw_data
                
                if isinstance(kline_list, list) and kline_list:
                    normalized_data = self._normalize_kline_data(kline_list, exchange)
                    all_normalized_data = normalized_data + all_normalized_data
                    end_timestamp = normalized_data[0]['timestamp'] - 1
                    remaining_limit -= len(normalized_data)
                    page_num += 1
                    if len(normalized_data) < fetch_limit: break
                else:
                    break
            except Exception as e:
                logger.warning(f"Request failed during pagination for {exchange} ({symbol}@{timeframe}): {e}")
                break
        
        if all_normalized_data:
            return all_normalized_data[-limit:]
        
        return None

    async def get_first_successful_klines(self, symbol: str, timeframe: str, limit: int = 200) -> Optional[Tuple[pd.DataFrame, str]]:
        exchanges = self.exchange_config.keys() # Automatically use all configured exchanges
        
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
                    for task in tasks: task.cancel()
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
