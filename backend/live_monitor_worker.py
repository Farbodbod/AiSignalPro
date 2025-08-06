# engines/live_monitor_worker.py (v18.0 - Multi-Timeframe Enabled)
import asyncio, logging, os, django, time
from typing import Dict, Tuple

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trading_app.settings')
django.setup()

from core.exchange_fetcher import ExchangeFetcher
from engines.master_orchestrator import MasterOrchestrator
from engines.signal_adapter import SignalAdapter
from engines.telegram_handler import TelegramHandler

ANALYSIS_PAIRS = [('15m', '1h'), ('1h', '4h')]
SYMBOLS_TO_MONITOR = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT', 'DOGE/USDT']
POLL_INTERVAL_SECONDS = 900
SIGNAL_CACHE_TTL_MAP = {'15m': 3*3600, '1h': 6*3600, '4h': 12*3600, 'default': 4*3600}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(module)s:%(funcName)s] - %(message)s')

class SignalCache:
    def __init__(self, ttl_map: Dict[str, int]): self._cache: Dict[Tuple[str, str, str], float] = {}; self.ttl_map = ttl_map
    def is_duplicate(self, symbol: str, timeframe: str, direction: str) -> bool:
        key = (symbol, timeframe, direction); ttl = self.ttl_map.get(timeframe, self.ttl_map['default'])
        if key in self._cache and (time.time() - self._cache[key]) < ttl:
            logging.info(f"Duplicate signal {key} found. Cooldown active for {((self._cache[key] + ttl) - time.time()) / 60:.1f} min.")
            return True
        return False
    def store_signal(self, symbol: str, timeframe: str, direction: str): self._cache[(symbol, timeframe, direction)] = time.time()

async def analyze_pair_and_alert(fetcher, orchestrator, telegram, cache, symbol, ltf, htf):
    try:
        logging.info(f"Fetching data for MTF analysis: {symbol} on {ltf} (confirmation from {htf})")
        ltf_task = fetcher.get_first_successful_klines(symbol, ltf, limit=200)
        htf_task = fetcher.get_first_successful_klines(symbol, htf, limit=200)
        results = await asyncio.gather(ltf_task, htf_task)
        
        ltf_res, htf_res = results
        if not (ltf_res and ltf_res[0] is not None and htf_res and htf_res[0] is not None):
            logging.warning(f"Could not fetch complete MTF data for {symbol} ({ltf}/{htf}).")
            return

        df_ltf, source_ltf = ltf_res
        df_htf, source_htf = htf_res
        
        final_signal_package = orchestrator.run_full_pipeline(df_ltf, ltf, df_htf, htf, symbol)

        if final_signal_package:
            base_signal = final_signal_package.get("base_signal", {}); direction = base_signal.get("direction")
            if cache.is_duplicate(symbol, ltf, direction): return
            adapter = SignalAdapter(signal_package=final_signal_package); message = adapter.to_telegram_message()
            logging.info(f"🚀🚀 MTF SIGNAL DETECTED! Preparing alert for {symbol} {ltf}/{htf} 🚀🚀")
            success = await telegram.send_message_async(message)
            if success: cache.store_signal(symbol, ltf, direction)
    except Exception as e:
        logging.error(f"Error during MTF analysis for {symbol} {ltf}/{htf}: {e}", exc_info=True)

async def main_loop():
    fetcher = ExchangeFetcher(); orchestrator = MasterOrchestrator(); telegram = TelegramHandler()
    signal_cache = SignalCache(ttl_map=SIGNAL_CACHE_TTL_MAP)
    await telegram.send_message_async("✅ *AiSignalPro Bot (v18.0 - MTF Enabled) is now LIVE!*")
    
    while True:
        logging.info("--- Starting new MTF monitoring cycle ---")
        tasks = [
            analyze_pair_and_alert(fetcher, orchestrator, telegram, signal_cache, symbol, ltf, htf)
            for symbol in SYMBOLS_TO_MONITOR
            for ltf, htf in ANALYSIS_PAIRS
        ]
        await asyncio.gather(*tasks)
        logging.info(f"--- Full MTF cycle finished. Sleeping for {POLL_INTERVAL_SECONDS} seconds... ---")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)

if __name__ == "__main__":
    try: asyncio.run(main_loop())
    except KeyboardInterrupt: logging.info("Bot stopped by user.")
