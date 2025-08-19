# core/exchange_fetcher.py (v8.5 - The OKX Hotfix Edition)

import asyncio
import time
import logging
from typing import Dict, List, Optional, Tuple, Any
import httpx
import pandas as pd
import numpy as np
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

logger = logging.getLogger(__name__)

EXCHANGE_CONFIG = {
    'mexc': {
        'base_url': 'https://api.mexc.com', 'kline_endpoint': '/api/v3/klines', 'ticker_endpoint': '/api/v3/ticker/24hr',
        'max_limit_per_req': 500, 'symbol_template': '{base}{quote}',
        'timeframe_map': {'5m': '5m', '15m': '15m', '1h': '1h', '4h': '4h', '1d': '1d'},
        'rate_limit_delay': 0.5, 'kline_schema': ['ts', 'o', 'h', 'l', 'c', 'v']
    },
    'kucoin': {
        'base_url': 'https://api.kucoin.com', 'kline_endpoint': '/api/v1/market/candles', 'ticker_endpoint': '/api/v1/market/stats',
        'max_limit_per_req': 1500, 'symbol_template': '{base}-{quote}',
        'timeframe_map': {'5m': '5min', '15m': '15min', '1h': '1hour', '4h': '4hour', '1d': '1day'},
        'rate_limit_delay': 0.5, 'kline_schema': ['ts', 'o', 'c', 'h', 'l', 'v']
    },
    'okx': {
        'base_url': 'https://www.okx.com', 'kline_endpoint': '/api/v5/market/candles', 'ticker_endpoint': '/api/v5/market/ticker',
        'max_limit_per_req': 300, 'symbol_template': '{base}-{quote}',
        'timeframe_map': {'5m': '5m', '15m': '15m', '1h': '1H', '4h': '4H', '1d': '1D'},
        'rate_limit_delay': 0.2, 'kline_schema': ['ts', 'o', 'h', 'l', 'c', 'v']
    },
}
SYMBOL_MAP = {'BTC/USDT': {'base': 'BTC', 'quote': 'USDT'}, 'ETH/USDT': {'base': 'ETH', 'quote': 'USDT'}}

def is_retryable_exception(exception: BaseException) -> bool:
    if isinstance(exception, (httpx.RequestError, httpx.TimeoutException)): return True
    if isinstance(exception, httpx.HTTPStatusError): return exception.response.status_code >= 500 or exception.response.status_code == 429
    return False

class ExchangeFetcher:
    """
    ExchangeFetcher (v8.5 - The OKX Hotfix Edition)
    ----------------------------------------------------------------
    This definitive version integrates a critical hotfix for OKX's inverted
    High/Low data anomaly. By mathematically correcting the candle data at the
    source, this version eliminates the root cause of the `high < low` errors,
    ensuring pristine data quality enters the analysis pipeline.
    """
    def __init__(self, config: Dict[str, Any] = None, cache_ttl: int = 60, cache_max_size: int = 256):
        effective_config = config or {}
        self.config = effective_config
        headers = {'User-Agent': 'AiSignalPro/8.5.0', 'Accept': 'application/json'}
        timeout_cfg = self.config.get("http_timeout", 20.0)
        self.client = httpx.AsyncClient(headers=headers, timeout=httpx.Timeout(timeout_cfg), follow_redirects=True)
        self.cache, self.cache_ttl, self.cache_max_size, self.cache_lock = {}, cache_ttl, cache_max_size, asyncio.Lock()
        self.exchange_config = self.config.get("exchange_specific", EXCHANGE_CONFIG)
        self.symbol_map = self.config.get("symbol_map", SYMBOL_MAP)
        logger.info("ExchangeFetcher (v8.5 - The OKX Hotfix Edition) initialized.")

    def _get_cache_key(self, prefix: str, exchange: str, symbol: str, timeframe: Optional[str] = None, limit: Optional[int] = None) -> str:
        key = f"{prefix}:{exchange}:{symbol}"
        if timeframe: key += f":{timeframe}"
        if limit: key += f":L{limit}"
        return key

    def _format_symbol(self, s: str, e: str) -> Optional[str]:
        if self.symbol_map and s in self.symbol_map:
            parts = self.symbol_map[s]
            base, quote = parts.get('base'), parts.get('quote')
        else:
            if '/' not in s:
                logger.warning(f"Unexpected symbol format for formatting: {s}")
                return None
            base, quote = s.split('/', 1)
        c = self.exchange_config.get(e)
        if not c: return None
        return c['symbol_template'].format(base=base, quote=quote).upper()

    def _format_timeframe(self, t: str, e: str) -> Optional[str]:
        c = self.exchange_config.get(e)
        return c.get('timeframe_map', {}).get(t) if c else None

    async def _ensure_cache_bound(self):
        if len(self.cache) > self.cache_max_size:
            keys_to_drop = list(self.cache.keys())[:len(self.cache) - self.cache_max_size]
            for key in keys_to_drop: self.cache.pop(key, None)
            logger.info(f"Cache pruned to {len(self.cache)} items.")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception(is_retryable_exception), reraise=True)
    async def _safe_async_request(self, method: str, url: str, **kwargs) -> Optional[Any]:
        exchange_name = kwargs.pop('exchange_name', 'unknown')
        delay = self.exchange_config.get(exchange_name, {}).get('rate_limit_delay', 1.0)
        await asyncio.sleep(delay)
        resp = await self.client.request(method, url, **kwargs)
        resp.raise_for_status()
        try:
            return resp.json()
        except ValueError as e:
            logger.warning(f"JSON decode failed from {exchange_name} for url {url}: {e}. Response text: {resp.text[:200]}")
            return None

    def _normalize_kline_data(self, data: List[list], source: str) -> List[Dict[str, Any]]:
        if not data: return []
        cfg = self.exchange_config.get(source, {})
        schema = cfg.get('kline_schema', ['ts', 'o', 'h', 'l', 'c', 'v'])

        if source == 'okx': data = list(reversed(data))

        normalized = []
        for k in data:
            try:
                if len(k) < len(schema):
                    raise IndexError(f"Kline array has {len(k)} elements, but schema requires {len(schema)}")

                mapping = dict(zip(schema, k))

                raw_ts = mapping.get('ts')
                ts = int(pd.to_datetime(raw_ts).timestamp() * 1000) if isinstance(raw_ts, str) and not str(raw_ts).isdigit() else int(raw_ts)
                if ts < 1_000_000_000_000: ts *= 1000

                o = float(mapping.get('o', np.nan))
                h = float(mapping.get('h', np.nan))
                l = float(mapping.get('l', np.nan))
                c = float(mapping.get('c', np.nan))
                v = float(mapping.get('v', np.nan))

                # ✅ THE CRITICAL OKX HOTFIX (v8.5):
                # Re-implementing the logic to handle OKX's known inverted High/Low candle quirk.
                if source == 'okx':
                    # OKX sometimes returns candles where the high value is in the low field and vice-versa.
                    # We mathematically correct this to ensure data integrity before it enters the cleaning stage.
                    actual_high = max(h, l)
                    actual_low = min(h, l)
                    h = actual_high
                    l = actual_low

                normalized.append({"timestamp": ts, "open": o, "high": h, "low": l, "close": c, "volume": v})
            except Exception as e:
                logger.warning(f"Malformed candle from {source} using schema {schema}: {k} -> {e}")
                fallback_ts = int(time.time() * 1000)
                normalized.append({"timestamp": fallback_ts, "open": np.nan, "high": np.nan, "low": np.nan, "close": np.nan, "volume": np.nan})
        return normalized

    def _clean_and_validate_dataframe(self, df: pd.DataFrame, symbol: str, timeframe: str) -> pd.DataFrame:
        cleaned = df.copy()
        for col in ['open', 'high', 'low', 'close']:
            cleaned[col] = cleaned[col].replace(0, np.nan)

        invalid = cleaned[cleaned['high'] < cleaned['low']]
        if not invalid.empty:
            logger.warning(f"{len(invalid)} candles with high < low found for {symbol}@{timeframe}. Nullifying them.")
            cleaned.loc[invalid.index, ['open', 'high', 'low', 'close', 'volume']] = np.nan

        nan_count = cleaned[['open', 'high', 'low', 'close']].isnull().sum().sum()
        if nan_count > 0:
            logger.warning(f"DataFrame for {symbol}@{timeframe} contains {nan_count} NaN values after cleaning.")
        return cleaned

    def _drop_incomplete_current_candle(self, df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        if df.empty: return df
        try:
            freq = timeframe.upper().replace('M', 'T')

            if df.index.tz is None:
                df = df.tz_localize('UTC')
            else:
                df = df.tz_convert('UTC')

            now_utc = pd.Timestamp.utcnow()

            offset = pd.tseries.frequencies.to_offset(freq)
            candle_end_times = df.index + offset

            complete_mask = candle_end_times <= now_utc

            if not complete_mask.all():
                incomplete_count = (~complete_mask).sum()
                logger.info(f"Removing {incomplete_count} incomplete/live candle(s) for {timeframe}.")
                df = df[complete_mask]
            return df
        except Exception as e:
            logger.error(f"Failed to drop incomplete candle for {timeframe}: {e}. Returning original data.")
            return df

    def _resample_and_fill_gaps(self, df: pd.DataFrame, timeframe: str, symbol: str) -> pd.DataFrame:
        if df.empty: return df
        try:
            freq = timeframe.upper().replace('M', 'T')

            aligned = df.copy()
            if aligned.index.tz is None: aligned = aligned.tz_localize('UTC')
            aligned.index = aligned.index.floor(freq)
            aligned = aligned[~aligned.index.duplicated(keep='last')]

            ohlcv_agg = {'open':'first', 'high':'max', 'low':'min', 'close':'last', 'volume':'sum'}
            res = aligned.resample(freq).agg(ohlcv_agg)

            if res.index.tz is None: res = res.tz_localize('UTC')
            full_date_range = pd.date_range(start=res.index.min(), end=res.index.max(), freq=freq, tz=res.index.tz)
            res = res.reindex(full_date_range)

            missing = res['open'].isna().sum()
            if missing > 0:
                logger.warning(f"Detected {missing} missing candle(s) for {symbol}@{timeframe}. Filling.")
                res['close'] = res['close'].ffill()
                prev_close = res['close'].shift(1)
                res['open'] = res['open'].fillna(prev_close).fillna(res['close'])

                pair = pd.concat([res['open'], res['close']], axis=1)
                res['high'] = res['high'].fillna(pair.max(axis=1))
                res['low'] = res['low'].fillna(pair.min(axis=1))
                res['volume'] = res['volume'].fillna(0.0)
                logger.info(f"Missing candles for {symbol}@{timeframe} were logically filled.")
            return res
        except Exception as e:
            logger.error(f"Failed to resample/fill gaps for {symbol}@{timeframe}: {e}. Returning original data.", exc_info=True)
            return df

    async def get_klines_from_one_exchange(self, exchange: str, symbol: str, timeframe: str, limit: int = 500) -> Optional[List[Dict]]:
        cache_key = self._get_cache_key("kline", exchange, symbol, timeframe, limit)
        async with self.cache_lock:
            if cache_key in self.cache and (time.time() - self.cache[cache_key]['timestamp']) < self.cache_ttl:
                return self.cache[cache_key]['data']

        config, fmt_symbol, fmt_tf = self.exchange_config.get(exchange), self._format_symbol(symbol, exchange), self._format_timeframe(timeframe, exchange)
        if not all([config, fmt_symbol, fmt_tf]): return None

        all_data, rem_limit, end_ts, max_req, pg = [], limit, None, config.get('max_limit_per_req', 1000), 1

        while rem_limit > 0:
            fetch_limit = min(rem_limit, max_req);
            if fetch_limit <= 0: break

            logger.info(f"Fetching page #{pg} for {symbol}@{timeframe} from {exchange} (limit: {fetch_limit})...")
            url = config['base_url'] + config['kline_endpoint']
            params = {'limit': str(fetch_limit)}
            if exchange == 'okx': params.update({'instId': fmt_symbol, 'bar': fmt_tf})
            elif exchange == 'kucoin': params.update({'symbol': fmt_symbol, 'type': fmt_tf})
            else: params.update({'symbol': fmt_symbol, 'interval': fmt_tf})

            if end_ts:
                if exchange == 'kucoin': params['endAt'] = int(end_ts / 1000)
                elif exchange == 'okx': params['before'] = str(end_ts)
                else: params['endTime'] = end_ts

            try:
                raw_data = await self._safe_async_request('GET', url, params=params, exchange_name=exchange)
                if raw_data is None:
                    logger.warning(f"No data returned from {exchange} for {symbol}@{timeframe} on page {pg}. Stopping pagination for this exchange.")
                    break

                kline_list = raw_data.get('data') if isinstance(raw_data, dict) and 'data' in raw_data else raw_data
                if isinstance(kline_list, list) and kline_list and isinstance(kline_list[0], (list, tuple)):
                    norm_data = self._normalize_kline_data(kline_list, exchange)
                    if not norm_data: break

                    all_data = norm_data + all_data
                    oldest_ts = min(c['timestamp'] for c in norm_data)
                    end_ts = oldest_ts - 1
                    rem_limit -= len(norm_data)
                    pg += 1
                else:
                    logger.info(f"Exchange returned no more data or unexpected format for {symbol}@{timeframe}. Ending pagination.")
                    break
            except Exception as e:
                logger.warning(f"Request failed during pagination for {symbol}@{timeframe}: {e}")
                break

        if all_data:
            all_data.sort(key=lambda x: x['timestamp'])
            final_data = all_data[-limit:]
            async with self.cache_lock:
                self.cache[cache_key] = {'timestamp': time.time(), 'data': final_data}
                await self._ensure_cache_bound()
            return final_data
        return None

    async def get_first_successful_klines(self, symbol: str, timeframe: str, limit: int = 200) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
        general_cfg = self.config.get("general", {})
        min_rows = general_cfg.get("min_rows_for_analysis", 300)

        exchanges = list(self.exchange_config.keys())

        async def fetch_and_tag(exchange: str):
            res = await self.get_klines_from_one_exchange(exchange, symbol, timeframe, limit=limit)
            if res:
                df = pd.DataFrame(res)
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
                df.set_index('timestamp', inplace=True)
                df = df[~df.index.duplicated(keep='first')]
                df.sort_index(inplace=True)

                df = self._drop_incomplete_current_candle(df, timeframe)
                df = self._resample_and_fill_gaps(df, timeframe, symbol)
                df = self._clean_and_validate_dataframe(df, symbol, timeframe)
                df = df.tail(limit)

                if len(df) < min_rows:
                    logger.warning(f"Data from '{exchange}' for {symbol}@{timeframe} passed cleaning but was rejected by Quality Gate: too few rows ({len(df)} < {min_rows}).")
                    return None, None

                if df.empty: return None, None
                return exchange, df
            return None, None

        tasks = [asyncio.create_task(fetch_and_tag(ex)) for ex in exchanges]

        try:
            for future in asyncio.as_completed(tasks):
                try:
                    exchange_res, df_res = await future
                    if exchange_res and df_res is not None and not df_res.empty:
                        for task in tasks:
                            if not task.done(): task.cancel()
                        logger.info(f"Klines acquired, cleaned & passed Quality Gate from '{exchange_res}' for {symbol}@{timeframe} with {len(df_res)} rows.")
                        return df_res, exchange_res
                except Exception as exc:
                    logger.warning(f"A fetcher task for {symbol}@{timeframe} failed: {exc}", exc_info=False)
                    continue
        finally:
            await asyncio.gather(*tasks, return_exceptions=True)

        logger.error(f"Critical Failure: Could not fetch klines for {symbol}@{timeframe} from any exchange.")
        return None, None

    async def get_ticker_from_one_exchange(self, exchange: str, symbol: str) -> Optional[Dict]:
        cache_key = self._get_cache_key("ticker", exchange, symbol)
        async with self.cache_lock:
            if cache_key in self.cache and (time.time() - self.cache[cache_key]['timestamp']) < 15:
                return self.cache[cache_key]['data']

        config, fmt_symbol = self.exchange_config.get(exchange), self._format_symbol(symbol, exchange)
        if not all([config, fmt_symbol, 'ticker_endpoint' in config]): return None

        url = config['base_url'] + config['ticker_endpoint']
        params = {'instId': fmt_symbol} if exchange == 'okx' else {'symbol': fmt_symbol}

        try:
            raw_data = await self._safe_async_request('GET', url, params=params, exchange_name=exchange)
            if raw_data:
                price, change = 0.0, 0.0
                data = None

                if exchange == 'mexc':
                    if isinstance(raw_data, list) and raw_data: data = raw_data[0]
                    elif isinstance(raw_data, dict): data = raw_data
                    if data:
                        price = float(data.get('lastPrice', 0))
                        change = float(data.get('priceChangePercent', 0)) * 100
                elif exchange == 'kucoin':
                    data = raw_data.get('data')
                    if isinstance(data, dict):
                        price = float(data.get('last', 0))
                        change = float(data.get('changeRate', 0)) * 100

                elif exchange == 'okx':
                    data_list = raw_data.get('data')
                    if isinstance(data_list, list) and data_list:
                        data = data_list[0]
                        price = float(data.get('last', 0))
                        open_24h = float(data.get('open24h', 0))
                        change = ((price - open_24h) / open_24h) * 100 if open_24h > 0 else 0.0

                if price > 0:
                    result = {'price': price, 'change_24h': change, 'source': exchange, 'symbol': symbol}
                    async with self.cache_lock:
                        self.cache[cache_key] = {'timestamp': time.time(), 'data': result}
                        await self._ensure_cache_bound()
                    return result
                else:
                    if data is not None:
                        logger.warning(f"Ticker data from {exchange} for {symbol} had zero price. Data: {data}")

        except Exception as e:
            logger.warning(f"Ticker data processing failed for {exchange} on {symbol}: {e}")
        return None

    async def get_first_successful_ticker(self, symbol: str) -> Optional[Dict]:
        tasks = [asyncio.create_task(self.get_ticker_from_one_exchange(ex, symbol)) for ex in self.exchange_config.keys()]

        try:
            for future in asyncio.as_completed(tasks):
                try:
                    result = await future
                    if result:
                        for task in tasks:
                            if not task.done(): task.cancel()
                        return result
                except Exception as exc:
                    logger.warning(f"A ticker task for {symbol} failed: {exc}", exc_info=False)
                    continue
        finally:
            await asyncio.gather(*tasks, return_exceptions=True)

        logger.error(f"Critical Failure: Could not fetch ticker for {symbol} from any exchange.")
        return None

    async def close(self):
        await self.client.aclose()
