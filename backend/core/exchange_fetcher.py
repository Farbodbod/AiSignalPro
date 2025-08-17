# core/exchange_fetcher.py (v5.8 - Definitive Peer-Reviewed Edition)

import asyncio
import time
import logging
from typing import Dict, List, Optional, Tuple, Any

import httpx
import pandas as pd
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
)

logger = logging.getLogger(__name__)

# Default configs remain for standalone robustness
EXCHANGE_CONFIG = {
    "mexc": {
        "base_url": "https://api.mexc.com",
        "kline_endpoint": "/api/v3/klines",
        "ticker_endpoint": "/api/v3/ticker/24hr",
        "max_limit_per_req": 500,
        "symbol_template": "{base}{quote}",
        "timeframe_map": {"5m": "5m", "15m": "15m", "1h": "1h", "4h": "4h", "1d": "1d"},
        "rate_limit_delay": 0.5,
    },
    "kucoin": {
        "base_url": "https://api.kucoin.com",
        "kline_endpoint": "/api/v1/market/candles",
        "ticker_endpoint": "/api/v1/market/stats",
        "max_limit_per_req": 1500,
        "symbol_template": "{base}-{quote}",
        "timeframe_map": {
            "5m": "5min",
            "15m": "15min",
            "1h": "1hour",
            "4h": "4hour",
            "1d": "1day",
        },
        "rate_limit_delay": 0.5,
    },
    "okx": {
        "base_url": "https://www.okx.com",
        "kline_endpoint": "/api/v5/market/candles",
        "ticker_endpoint": "/api/v5/market/ticker",
        "max_limit_per_req": 300,
        "symbol_template": "{base}-{quote}",
        "timeframe_map": {
            "5m": "5m",
            "15m": "15m",
            "1h": "1H",
            "4h": "4H",
            "1d": "1D",
        },
        "rate_limit_delay": 0.2,
    },
}

SYMBOL_MAP = {
    "BTC/USDT": {"base": "BTC", "quote": "USDT"},
    "ETH/USDT": {"base": "ETH", "quote": "USDT"},
}


def is_retryable_exception(exception: BaseException) -> bool:
    """Return True if we should retry, False otherwise."""
    if isinstance(exception, (httpx.RequestError, httpx.TimeoutException)):
        return True
    if isinstance(exception, httpx.HTTPStatusError):
        return (
            exception.response.status_code >= 500
            or exception.response.status_code == 429
        )
    return False


class ExchangeFetcher:
    def __init__(
        self,
        config: Dict[str, Any] = None,
        cache_ttl: int = 60,
        cache_max_size: int = 256,
    ):
        headers = {"User-Agent": "AiSignalPro/5.8.0", "Accept": "application/json"}
        self.client = httpx.AsyncClient(
            headers=headers, timeout=20, follow_redirects=True
        )
        self.cache = {}
        self.cache_ttl = cache_ttl
        self.cache_max_size = cache_max_size
        self.cache_lock = asyncio.Lock()

        effective_config = config or {}
        self.exchange_config = effective_config.get(
            "exchange_specific", EXCHANGE_CONFIG
        )
        self.symbol_map = effective_config.get("symbol_map", SYMBOL_MAP)

        logger.info("ExchangeFetcher (v5.8 - Definitive) initialized.")

    def _get_cache_key(
        self,
        prefix: str,
        exchange: str,
        symbol: str,
        timeframe: Optional[str] = None,
    ) -> str:
        key = f"{prefix}:{exchange}:{symbol}"
        return key + f":{timeframe}" if timeframe else key

    def _format_symbol(self, s: str, e: str) -> Optional[str]:
        if self.symbol_map and s in self.symbol_map:
            parts = self.symbol_map[s]
            base, quote = parts.get("base"), parts.get("quote")
        else:
            if "/" not in s:
                logger.warning(f"Unexpected symbol format for formatting: {s}")
                return None
            base, quote = s.split("/", 1)

        c = self.exchange_config.get(e)
        if not c:
            return None
        return c["symbol_template"].format(base=base, quote=quote).upper()

    def _format_timeframe(self, t: str, e: str) -> Optional[str]:
        c = self.exchange_config.get(e)
        return c.get("timeframe_map", {}).get(t) if c else None

    async def _ensure_cache_bound(self):
        if len(self.cache) > self.cache_max_size:
            keys_to_drop = list(self.cache.keys())[
                : len(self.cache) - self.cache_max_size
            ]
            for key in keys_to_drop:
                self.cache.pop(key, None)
            logger.info(f"Cache pruned to {len(self.cache)} items.")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception(is_retryable_exception),
        reraise=True,
    )
    async def _safe_async_request(
        self, method: str, url: str, **kwargs
    ) -> Optional[Any]:
        exchange_name = kwargs.pop("exchange_name", "unknown")
        delay = self.exchange_config.get(exchange_name, {}).get(
            "rate_limit_delay", 1.0
        )
        await asyncio.sleep(delay)
        response = await self.client.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()

    def _normalize_kline_data(
        self, data: List[list], source: str
    ) -> List[Dict[str, Any]]:
        if not data:
            return []
        normalized_data = []
        if source == "okx":
            data.reverse()

        for k in data:
            try:
                raw_ts = k[0]
                if isinstance(raw_ts, str) and not raw_ts.isdigit():
                    ts_int = int(pd.to_datetime(raw_ts).timestamp() * 1000)
                else:
                    ts_int = int(raw_ts)

                if ts_int < 1_000_000_000_000:
                    ts_int *= 1000

                candle = {
                    "timestamp": ts_int,
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                }
                normalized_data.append(candle)
            except (ValueError, TypeError, IndexError) as e:
                logger.warning(
                    f"Skipping malformed candle from {source}: {k}. Error: {e}"
                )
        return normalized_data

    async def get_klines_from_one_exchange(
        self, exchange: str, symbol: str, timeframe: str, limit: int = 500
    ) -> Optional[List[Dict]]:
        cache_key = self._get_cache_key("kline", exchange, symbol, timeframe)
        async with self.cache_lock:
            if (
                cache_key in self.cache
                and (time.time() - self.cache[cache_key]["timestamp"])
                < self.cache_ttl
            ):
                logger.info(
                    f"Serving {len(self.cache[cache_key]['data'])} klines for {symbol} from cache ({exchange})."
                )
                return self.cache[cache_key]["data"]

        config = self.exchange_config.get(exchange)
        fmt_symbol = self._format_symbol(symbol, exchange)
        fmt_tf = self._format_timeframe(timeframe, exchange)
        if not all([config, fmt_symbol, fmt_tf]):
            return None

        all_data, rem_limit, end_ts = [], limit, None
        max_req = config.get("max_limit_per_req", 1000)
        pg = 1

        while rem_limit > 0:
            fetch_limit = min(rem_limit, max_req)
            if fetch_limit <= 0:
                break

            logger.info(
                f"Fetching page #{pg} for {symbol}@{timeframe} from {exchange} (limit: {fetch_limit})..."
            )
            url = config["base_url"] + config["kline_endpoint"]
            params = {"limit": str(fetch_limit)}

            if exchange == "okx":
                params.update({"instId": fmt_symbol, "bar": fmt_tf})
            elif exchange == "kucoin":
                params.update({"symbol": fmt_symbol, "type": fmt_tf})
            else:
                params.update({"symbol": fmt_symbol, "interval": fmt_tf})

            if end_ts:
                if exchange == "kucoin":
                    params["endAt"] = int(end_ts / 1000)
                elif exchange == "okx":
                    params["before"] = str(end_ts)
                else:
                    params["endTime"] = end_ts

            try:
                raw_data = await self._safe_async_request(
                    "GET", url, params=params, exchange_name=exchange
                )
                if raw_data is None:
                    break

                kline_list = (
                    raw_data.get("data")
                    if isinstance(raw_data, dict) and "data" in raw_data
                    else raw_data
                )

                if isinstance(kline_list, list) and kline_list:
                    norm_data = self._normalize_kline_data(kline_list, exchange)
                    if not norm_data:
                        break
                    all_data = norm_data + all_data
                    end_ts = norm_data[0]["timestamp"] - 1
                    rem_limit -= len(norm_data)
                    pg += 1
                else:
                    logger.info(
                        "Exchange returned no more data. Ending pagination."
                    )
                    break
            except Exception as e:
                logger.warning(f"Request failed during pagination: {e}")
                break

        if all_data:
            async with self.cache_lock:
                self.cache[cache_key] = {
                    "timestamp": time.time(),
                    "data": all_data,
                }
                await self._ensure_cache_bound()
            return all_data[-limit:]
        return None

    async def get_first_successful_klines(
        self, symbol: str, timeframe: str, limit: int = 200
    ) -> Optional[Tuple[pd.DataFrame, str]]:
        exchanges = list(self.exchange_config.keys())

        async def fetch_and_tag(exchange: str):
            res = await self.get_klines_from_one_exchange(
                exchange, symbol, timeframe, limit=limit
            )
            if res:
                df = pd.DataFrame(res)
                df["timestamp"] = pd.to_datetime(
                    df["timestamp"], unit="ms", utc=True
                )
                df.set_index("timestamp", inplace=True)
                df = df[~df.index.duplicated(keep="first")]
                df.sort_index(inplace=True)
                return exchange, df
            return None

        tasks = [asyncio.create_task(fetch_and_tag(ex)) for ex in exchanges]

        try:
            for future in asyncio.as_completed(tasks):
                result_tuple = await future
                if result_tuple:
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    source, df = result_tuple
                    logger.info(
                        f"Klines acquired from '{source}' for {symbol}@{timeframe} with {len(df)} rows."
                    )
                    return df, source
        finally:
            await asyncio.gather(*tasks, return_exceptions=True)

        logger.error(
            f"Critical Failure: Could not fetch klines for {symbol}@{timeframe} from any exchange."
        )
        return None, None

    async def get_ticker_from_one_exchange(
        self, exchange: str, symbol: str
    ) -> Optional[Dict]:
        cache_key = self._get_cache_key("ticker", exchange, symbol)
        async with self.cache_lock:
            if (
                cache_key in self.cache
                and (time.time() - self.cache[cache_key]["timestamp"])
                < 15
            ):
                return self.cache[cache_key]["data"]

        config = self.exchange_config.get(exchange)
        fmt_symbol = self._format_symbol(symbol, exchange)
        if not all([config, fmt_symbol, "ticker_endpoint" in config]):
            return None

        url = config["base_url"] + config["ticker_endpoint"]
        params = (
            {"instId": fmt_symbol}
            if exchange == "okx"
            else {"symbol": fmt_symbol}
        )

        try:
            raw_data = await self._safe_async_request(
                "GET", url, params=params, exchange_name=exchange
            )
            if raw_data:
                price, change = 0.0, 0.0

                if exchange == "mexc":
                    data = (
                        raw_data[0]
                        if isinstance(raw_data, list) and raw_data
                        else raw_data
                    )
                    price = float(data.get("lastPrice", 0))
                    change = (
                        float(data.get("priceChangePercent", 0)) * 100
                    )

                elif exchange == "kucoin" and raw_data.get("data"):
                    data = raw_data["data"]
                    price = float(data.get("last", 0))
                    change = float(data.get("changeRate", 0)) * 100

                elif exchange == "okx" and raw_data.get("data"):
                    data = raw_data["data"][0]
                    price = float(data.get("last", 0))
                    open_24h = float(data.get("open24h", 0))
                    change = (
                        ((price - open_24h) / open_24h) * 100
                        if open_24h > 0
                        else 0.0
                    )

                if price > 0:
                    result = {
                        "price": price,
                        "change_24h": change,
                        "source": exchange,
                        "symbol": symbol,
                    }
                    async with self.cache_lock:
                        self.cache[cache_key] = {
                            "timestamp": time.time(),
                            "data": result,
                        }
                        await self._ensure_cache_bound()
                    return result

        except Exception as e:
            logger.warning(
                f"Ticker data processing failed for {exchange} on {symbol}: {e}"
            )
        return None

    async def get_first_successful_ticker(self, symbol: str) -> Optional[Dict]:
        tasks = [
            asyncio.create_task(
                self.get_ticker_from_one_exchange(ex, symbol)
            )
            for ex in self.exchange_config.keys()
        ]
        try:
            for future in asyncio.as_completed(tasks):
                result = await future
                if result:
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    return result
        finally:
            await asyncio.gather(*tasks, return_exceptions=True)

        logger.error(
            f"Critical Failure: Could not fetch ticker for {symbol} from any exchange."
        )
        return None

    async def close(self):
        await self.client.aclose()
