import time
import logging
import pandas as pd
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trading_app.settings')
django.setup()

from core.exchange_fetcher import ExchangeFetcher
from engines.master_orchestrator import MasterOrchestrator
from engines.signal_adapter import SignalAdapter
from engines.telegram_handler import TelegramHandler
from core.views import convert_numpy_types

SYMBOLS_TO_MONITOR = ['BTC-USDT', 'ETH-USDT', 'SOL-USDT']
POLL_INTERVAL_SECONDS = 300
SIGNAL_CACHE_TTL_SECONDS = 1800

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class SignalCache:
    def __init__(self, ttl_seconds: int):
        self.cache = {}
        self.ttl = ttl_seconds
    def is_duplicate(self, symbol: str, signal_type: str) -> bool:
        now = time.time()
        if symbol in self.cache:
            last_signal, last_time = self.cache[symbol]
            if signal_type == last_signal and (now - last_time) < self.ttl:
                return True
        return False
    def store(self, symbol: str, signal_type: str):
        self.cache[symbol] = (signal_type, time.time())

def format_professional_message(signal_obj: dict) -> str:
    signal_type = signal_obj.get("signal_type", "N/A")
    symbol = signal_obj.get("symbol", "N/A")
    price = signal_obj.get("current_price", 0.0)
    confidence = signal_obj.get("confidence", 0)
    risk = signal_obj.get("risk_level", "N/A")
    scores = signal_obj.get("scores", {})
    buy_score = scores.get("buy_score", 0)
    sell_score = scores.get("sell_score", 0)
    tags = ", ".join(signal_obj.get("tags", ["No specific factors"]))
    message = (
        f"SIGNAL ALERT: *{signal_type} {symbol}*\n"
        f"----------------------------------------\n"
        f"🔹 *Price:* `${price:,.2f}`\n"
        f"🔸 *AI Confidence:* {confidence}%\n"
        f"💣 *Risk Level:* `{risk.upper()}`\n"
        f"📈 *Buy Score:* {buy_score:.2f}\n"
        f"📉 *Sell Score:* {sell_score:.2f}\n"
        f"🔍 *Key Factors:* `{tags}`\n"
        f"----------------------------------------"
    )
    return message
    
def _get_data_with_fallback_worker(fetcher, symbol, interval, limit, min_length):
    for source in ['kucoin', 'mexc', 'okx', 'gateio']:
        try:
            kline_data = fetcher.get_klines(source=source, symbol=symbol, interval=interval, limit=limit)
            if kline_data and len(kline_data) >= min_length:
                logging.info(f"Successfully fetched {len(kline_data)} candles from {source} for {symbol}.")
                return pd.DataFrame(kline_data), source
        except Exception as e:
            logging.warning(f"Could not fetch from {source} for {symbol}: {e}")
    return None, None

def monitor_loop():
    try:
        telegram = TelegramHandler()
        signal_cache = SignalCache(ttl_seconds=SIGNAL_CACHE_TTL_SECONDS)
        orchestrator = MasterOrchestrator()
        fetcher = ExchangeFetcher()
        logging.info("Live Monitoring Worker started successfully.")
        telegram.send_message("*✅ ربات مانیتورینگ حرفه‌ای فعال شد.*")
    except Exception as e:
        logging.error(f"Failed to start worker: {e}", exc_info=True)
        return

    while True:
        logging.info("--- Starting New Monitoring Cycle ---")
        for symbol in SYMBOLS_TO_MONITOR:
            try:
                logging.info(f"Analyzing {symbol}...")
                
                all_tf_analysis = {}
                timeframes_to_analyze = ['5m', '15m', '1h', '4h', '1d']
                for tf in timeframes_to_analyze:
                    limit = 300 if tf in ['1h', '4h', '1d'] else 100
                    min_length = 200 if tf in ['1h', '4h', '1d'] else 50
                    df, source = _get_data_with_fallback_worker(fetcher, symbol, tf, limit=limit, min_length=min_length)
                    if df is not None:
                        analysis = orchestrator.analyze_single_dataframe(df, tf)
                        analysis['source'] = source
                        analysis['symbol'] = symbol
                        analysis['interval'] = tf
                        all_tf_analysis[tf] = analysis
                
                if not all_tf_analysis:
                    logging.warning(f"Could not fetch enough data for {symbol} on any timeframe.")
                    continue

                raw_orchestrator_result = orchestrator.get_multi_timeframe_signal(all_tf_analysis)
                
                adapter = SignalAdapter(analytics_output=raw_orchestrator_result, strategy='balanced')
                signal_obj = adapter.combine()
                
                signal_type = signal_obj.get("signal_type")
                if signal_type and signal_type != "HOLD":
                    if not signal_cache.is_duplicate(symbol, signal_type):
                        signal_cache.store(symbol, signal_type)
                        professional_message = format_professional_message(signal_obj)
                        telegram.send_message(professional_message)
                        logging.info(f"Alert sent for {symbol}: {signal_type}")
                        time.sleep(5)
                    else:
                        logging.info(f"Duplicate signal '{signal_type}' for {symbol}. Skipping alert.")
            except Exception as e:
                logging.error(f"Error processing symbol {symbol}: {e}", exc_info=True)
            
        logging.info(f"Cycle finished. Waiting for {POLL_INTERVAL_SECONDS} seconds.")
        time.sleep(POLL_INTERVAL_SECONDS)

if __name__ == "__main__":
    monitor_loop()

