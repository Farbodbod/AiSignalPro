# core/exchange_fetcher.py (v5.7 - Structured Logging Integration)

import asyncio
import time
import logging
from typing import Dict, List, Optional, Tuple, Any
import httpx
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential
import structlog # ✅ UPGRADE: Use structlog

# ✅ UPGRADE: Get logger via structlog for structured logging
logger = structlog.get_logger()

# Default configs remain for standalone robustness
EXCHANGE_CONFIG = {
    'mexc': {'base_url': 'https://api.mexc.com', 'kline_endpoint': '/api/v3/klines', 'ticker_endpoint': '/api/v3/ticker/24hr', 'max_limit_per_req': 500, 'symbol_template': '{base}{quote}', 'timeframe_map': {'5m': '5m', '15m': '15m', '1h': '1h', '4h': '4h', '1d': '1d'}, 'rate_limit_delay': 0.5},
    'kucoin': {'base_url': 'https://api.kucoin.com', 'kline_endpoint': '/api/v1/market/candles', 'ticker_endpoint': '/api/v1/market/stats', 'max_limit_per_req': 500, 'symbol_template': '{base}-{quote}', 'timeframe_map': {'5m': '5min', '15m': '15min', '1h': '1hour', '4h': '4hour', '1d': '1day'}, 'rate_limit_delay': 0.5},
    'okx': {'base_url': 'https://www.okx.com', 'kline_endpoint': '/api/v5/market/candles', 'ticker_endpoint': '/api/v5/market/ticker', 'max_limit_per_req': 500, 'symbol_template': '{base}-{quote}', 'timeframe_map': {'5m': '5m', '15m': '15m', '1h': '1H', '4h': '4H', '1d': '1D'}, 'rate_limit_delay': 0.2},
}
SYMBOL_MAP = {'BTC/USDT': {'base': 'BTC', 'quote': 'USDT'}, 'ETH/USDT': {'base': 'ETH', 'quote': 'USDT'}}

class ExchangeFetcher:
    def __init__(self, config: Dict[str, Any] = None, cache_ttl: int = 60):
        headers = {'User-Agent': 'AiSignalPro/5.7.0', 'Accept': 'application/json'}
        self.client = httpx.AsyncClient(headers=headers, timeout=20, follow_redirects=True)
        self.cache = {}
        self.cache_ttl = cache_ttl
        
        effective_config = config or {}
        self.exchange_config = effective_config.get("exchange_specific", EXCHANGE_CONFIG)
        self.symbol_map = effective_config.get("symbol_map", SYMBOL_MAP)
        
        # ✅ UPGRADE: Converted to structured log
        logger.info("ExchangeFetcher initialized", version="5.7.0", features=["Cache", "TenacityRetry"])

    # All private helper methods remain unchanged in their logic
    def _get_cache_key(self, prefix: str, exchange: str, symbol: str, timeframe: Optional[str] = None) -> str:
        key = f"{prefix}:{exchange}:{symbol}"; return key + f":{timeframe}" if timeframe else key

    def _format_symbol(self, s: str, e: str) -> Optional[str]:
        base_symbol, quote_symbol = s.split('/'); c = self.exchange_config.get(e); return c['symbol_template'].format(base=base_symbol, quote=quote_symbol).upper() if c else None

    def _format_timeframe(self, t: str, e: str) -> Optional[str]:
        c = self.exchange_config.get(e); return c.get('timeframe_map', {}).get(t) if c else None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=6), reraise=True)
    async def _safe_async_request(self, method: str, url: str, **kwargs) -> Optional[Any]:
        exchange_name = kwargs.pop('exchange_name', 'unknown'); delay = self.exchange_config.get(exchange_name, {}).get('rate_limit_delay', 1.0)
        await asyncio.sleep(delay); response = await self.client.request(method, url, **kwargs)
        response.raise_for_status(); return response.json()

    def _normalize_kline_data(self, data: List[list], source: str) -> List[Dict[str, Any]]:
        if not data: return []
        normalized_data = []
        if source == 'okx': data.reverse()
        for k in data:
            try:
                candle = {"timestamp": int(k[0]), "open": float(k[1]), "high": float(k[2]), "low": float(k[3]), "close": float(k[4]), "volume": float(k[5])}
                normalized_data.append(candle)
            except (ValueError, TypeError, IndexError):
                # ✅ UPGRADE: Converted to structured log
                logger.warning("Skipping malformed kline candle", source=source, raw_candle_data=k)
        return normalized_data

    async def get_klines_from_one_exchange(self, exchange: str, symbol: str, timeframe: str, limit: int = 500) -> Optional[List[Dict]]:
        cache_key = self._get_cache_key("kline", exchange, symbol, timeframe)
        if cache_key in self.cache and (time.time() - self.cache[cache_key]['timestamp']) < self.cache_ttl:
            # ✅ UPGRADE: Converted to structured log
            logger.info("Serving klines from cache", symbol=symbol, exchange=exchange, timeframe=timeframe, count=len(self.cache[cache_key]['data']))
            return self.cache[cache_key]['data']

        config, formatted_symbol, formatted_timeframe = self.exchange_config.get(exchange), self._format_symbol(symbol, exchange), self._format_timeframe(timeframe, exchange)
        if not all([config, formatted_symbol, formatted_timeframe]): return None
        
        all_normalized_data, remaining_limit, end_timestamp, page_num = [], limit, None, 1
        max_per_req = config.get('max_limit_per_req', 1000)

        while remaining_limit > 0:
            fetch_limit = min(remaining_limit, max_per_req)
            if fetch_limit <= 0: break
            
            # ✅ UPGRADE: Converted to structured log
            logger.info("Fetching kline page", page=page_num, symbol=symbol, timeframe=timeframe, exchange=exchange, limit=fetch_limit)
            
            url = config['base_url'] + config['kline_endpoint']; params = {'limit': str(fetch_limit)}
            if exchange == 'okx': params.update({'instId': formatted_symbol, 'bar': formatted_timeframe});
            elif exchange == 'kucoin': params.update({'symbol': formatted_symbol, 'type': formatted_timeframe});
            else: params.update({'symbol': formatted_symbol, 'interval': formatted_timeframe});
            
            if end_timestamp:
                if exchange == 'kucoin': params['endAt'] = int(end_timestamp / 1000)
                elif exchange == 'okx': params['before'] = str(end_timestamp)
                else: params['endTime'] = end_timestamp
            
            try:
                raw_data = await self._safe_async_request('GET', url, params=params, exchange_name=exchange)
                kline_list = raw_data.get('data') if isinstance(raw_data, dict) and 'data' in raw_data else raw_data
                
                if isinstance(kline_list, list) and kline_list:
                    normalized_data = self._normalize_kline_data(kline_list, exchange)
                    if not normalized_data: break
                    all_normalized_data = normalized_data + all_normalized_data
                    end_timestamp = normalized_data[0]['timestamp'] - 1
                    remaining_limit -= len(normalized_data); page_num += 1
                else:
                    logger.info("Pagination ended; no more data from exchange", exchange=exchange, symbol=symbol, timeframe=timeframe); break
            except Exception as e:
                logger.warning("Kline pagination request failed", exchange=exchange, symbol=symbol, timeframe=timeframe, error=str(e)); break
        
        if all_normalized_data:
            self.cache[cache_key] = {'timestamp': time.time(), 'data': all_normalized_data}; return all_normalized_data[-limit:]
        return None

    async def get_first_successful_klines(self, symbol: str, timeframe: str, limit: int = 200) -> Optional[Tuple[pd.DataFrame, str]]:
        exchanges = list(self.exchange_config.keys())
        async def fetch_and_tag(exchange: str):
            result = await self.get_klines_from_one_exchange(exchange, symbol, timeframe, limit=limit)
            if result: 
                df = pd.DataFrame(result); df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms'); df.set_index('timestamp', inplace=True)
                df = df[~df.index.duplicated(keep='first')]; return exchange, df
            return None
        tasks = [asyncio.create_task(fetch_and_tag(ex)) for ex in exchanges]
        
        try:
            for future in asyncio.as_completed(tasks):
                result_tuple = await future
                if result_tuple:
                    for task in tasks: 
                        if not task.done(): task.cancel()
                    source_exchange, df = result_tuple
                    # ✅ UPGRADE: Converted to structured log
                    logger.info("Klines acquired successfully", source_exchange=source_exchange, symbol=symbol, timeframe=timeframe, rows_acquired=len(df), rows_requested=limit)
                    return df, source_exchange
        except asyncio.CancelledError:
            logger.debug("Kline fetch tasks cancelled", symbol=symbol, reason="A successful fetch was completed")
        except Exception as e:
            logger.error("Unexpected error in get_first_successful_klines", symbol=symbol, timeframe=timeframe, error=str(e), exc_info=True)

        # ✅ UPGRADE: Converted to structured log
        logger.error("Critical kline fetch failure", symbol=symbol, timeframe=timeframe, exchanges_tried=exchanges)
        return None, None

    # The ticker-related methods are also updated to use structured logging
    async def get_ticker_from_one_exchange(self, exchange: str, symbol: str) -> Optional[Dict]:
        cache_key = self._get_cache_key("ticker", exchange, symbol)
        if cache_key in self.cache and (time.time() - self.cache[cache_key]['timestamp']) < 15:
            return self.cache[cache_key]['data']
        config, formatted_symbol = self.exchange_config.get(exchange), self._format_symbol(symbol, exchange)
        if not all([config, formatted_symbol, 'ticker_endpoint' in config]): return None
        url = config['base_url'] + config['ticker_endpoint']; params = {'instId': formatted_symbol} if exchange == 'okx' else {'symbol': formatted_symbol}
        
        try:
            raw_data = await self._safe_async_request('GET', url, params=params, exchange_name=exchange)
            if raw_data:
                price, change = 0.0, 0.0
                if exchange == 'mexc':
                    data = raw_data[0] if isinstance(raw_data, list) and raw_data else raw_data; price = float(data.get('lastPrice', 0)); change = float(data.get('priceChangePercent', 0)) * 100
                elif exchange == 'kucoin' and raw_data.get('data'):
                    data = raw_data['data']; price = float(data.get('last', 0)); change = float(data.get('changeRate', 0)) * 100
                elif exchange == 'okx' and raw_data.get('data'):
                    data = raw_data['data'][0]; price = float(data.get('last', 0)); open_price_24h = float(data.get('open24h', 0)); change = ((price - open_price_24h) / open_price_24h) * 100 if open_price_24h > 0 else 0.0
                if price > 0:
                    result = {'price': price, 'change_24h': change, 'source': exchange, 'symbol': symbol}; self.cache[cache_key] = {'timestamp': time.time(), 'data': result}; return result
        except Exception as e:
            # ✅ UPGRADE: Converted to structured log
            logger.warning("Ticker data processing failed", exchange=exchange, symbol=symbol, error=str(e))
        return None

    async def get_first_successful_ticker(self, symbol: str) -> Optional[Dict]:
        tasks = [asyncio.create_task(self.get_ticker_from_one_exchange(ex, symbol)) for ex in self.exchange_config.keys()]
        try:
            for future in asyncio.as_completed(tasks):
                result = await future
                if result:
                    for task in tasks:
                        if not task.done(): task.cancel()
                    return result
        except asyncio.CancelledError:
            logger.debug("Ticker fetch tasks cancelled", symbol=symbol, reason="A successful fetch was completed")
        except Exception as e:
            logger.error("Unexpected error in get_first_successful_ticker", symbol=symbol, error=str(e), exc_info=True)
            
        # ✅ UPGRADE: Converted to structured log
        logger.error("Critical ticker fetch failure", symbol=symbol, exchanges_tried=list(self.exchange_config.keys()))
        return None

    async def close(self):
        await self.client.aclose()
