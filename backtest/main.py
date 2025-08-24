# backtest/main.py (v1.0 - The Strategic Simulation Engine)

import pandas as pd
import logging
import json
import asyncio
from tqdm import tqdm

from .data_handler import DataHandler
from .portfolio import Portfolio
from .broker import Broker
from engines.master_orchestrator import MasterOrchestrator

# Configure logging for the backtest runner
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s',
    force=True
)
logger = logging.getLogger(__name__)

async def run_backtest(config: dict, symbol: str, timeframe: str, data_dir: str):
    """
    The main orchestrator for running a single, event-driven backtest.
    It connects all modular components and simulates the strategy's
    performance over historical data, candle by candle.
    """
    logger.info("="*60)
    logger.info(f"--- Initializing Backtest for {symbol} @ {timeframe} ---")
    logger.info("="*60)
    
    # 1. Initialize core components from the master config
    general_cfg = config.get("general", {})
    initial_equity = general_cfg.get("account_equity", 10000)
    risk_per_trade = 1.0  # Default 1% risk, can be moved to config later
    commission = general_cfg.get("assumed_fees_pct", 0.0006) * 100 # Convert to percent
    min_rows_for_analysis = general_cfg.get("min_rows_for_analysis", 300)

    data_handler = DataHandler(data_directory=data_dir)
    portfolio = Portfolio(initial_equity=initial_equity, risk_per_trade_percent=risk_per_trade, commission_pct=commission)
    broker = Broker(portfolio=portfolio, data_handler=data_handler)
    master_orchestrator = MasterOrchestrator(config=config)

    # 2. Load full historical data
    full_df = data_handler.load_data(symbol, timeframe)
    if full_df is None:
        logger.critical(f"BACKTEST SKIPPED: Data loading failed for {symbol}@{timeframe}.")
        return

    # ✅ UPGRADE 1: Indicator Warm-up Period
    # Ensure we have enough data to meet the minimum requirement before starting.
    if len(full_df) < min_rows_for_analysis:
        logger.critical(f"BACKTEST SKIPPED: Not enough data for {symbol}@{timeframe}. "
                        f"Required: {min_rows_for_analysis}, Available: {len(full_df)}")
        return

    logger.info(f"--- Starting Simulation for {symbol}@{timeframe} from {full_df.index.min()} to {full_df.index.max()} ---")
    logger.info(f"Warm-up period: First {min_rows_for_analysis} candles. Main loop starts after.")

    # 3. Main Event Loop
    # The loop starts after the warm-up period to ensure indicators are stable.
    for i in tqdm(range(min_rows_for_analysis, len(full_df)), desc=f"Simulating {symbol}@{timeframe}"):
        timestamp = full_df.index[i]
        current_candle = full_df.iloc[i]
        
        # A. Update portfolio equity based on the current candle's close price
        portfolio.on_candle(timestamp, {symbol: current_candle['close']})

        # ✅ UPGRADE 2: Optimized Lookback DataFrame
        # Create the historical view for the analysis engines
        historical_df = full_df.iloc[:i + 1]
        
        # ✅ UPGRADE 3: Precise Event Loop Data Flow
        # I. Run the full analysis pipeline
        analysis_package, _ = await master_orchestrator.run_analysis_pipeline(
            df=historical_df, symbol=symbol, timeframe=timeframe
        )
        if not analysis_package: continue

        # II. Run the strategy pipeline
        # For this backtester version, we pass the primary analysis as the only available context.
        htf_context = {timeframe: analysis_package}
        final_signal_package = await master_orchestrator.run_strategy_pipeline(
            primary_analysis=analysis_package, htf_context=htf_context, symbol=symbol, timeframe=timeframe
        )

        # III. Handle a successful signal
        if final_signal_package and final_signal_package.get("status") == "SUCCESS":
            base_signal = final_signal_package.get("base_signal", {})
            # Add context for the portfolio and broker
            base_signal.update({'timestamp': timestamp, 'symbol': symbol, 'timeframe': timeframe})

            # IV. Generate an order via the Portfolio (which uses the PositionSizer)
            order_event = portfolio.on_signal(base_signal)
            
            # V. Execute the order via the Broker
            if order_event:
                broker.execute_order(order_event, timestamp)
    
    logger.info(f"--- Simulation Complete for {symbol}@{timeframe} ---")
    
    # 4. Generate Final Performance Report
    portfolio.generate_performance_report()

async def run_all_backtests():
    """
    Main entry point to run backtests for all configured symbols and timeframes.
    """
    config_path = 'config.json'
    data_dir = 'historical_data' # Assuming data is in this directory
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        logger.critical(f"FATAL: Could not load master config file at '{config_path}': {e}")
        return

    # ✅ UPGRADE 4: Comprehensive Backtest Execution
    symbols_to_test = config.get("general", {}).get("symbols_to_monitor", [])
    timeframes_to_test = config.get("general", {}).get("timeframes_to_analyze", [])

    logger.info(f"Found {len(symbols_to_test)} symbols and {len(timeframes_to_test)} timeframes in config.")
    
    for symbol in symbols_to_test:
        for timeframe in timeframes_to_test:
            await run_backtest(config, symbol, timeframe, data_dir)

if __name__ == '__main__':
    asyncio.run(run_all_backtests())
