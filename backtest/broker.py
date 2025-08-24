# backtest/broker.py (v1.0 - The Precision Execution Engine)

import pandas as pd
import logging
import random
from typing import Dict, Any, Optional

# Forward reference for type hinting to avoid circular imports
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .portfolio import Portfolio
    from .data_handler import DataHandler

logger = logging.getLogger(__name__)

class Broker:
    """
    Simulates the actions of a real-world exchange with surgical precision.
    It executes orders based on next-candle data to prevent look-ahead bias,
    simulates realistic slippage and commission, and communicates via
    anti-fragile event contracts.
    """

    def __init__(self, portfolio: 'Portfolio', data_handler: 'DataHandler', 
                 base_slippage_pct: float = 0.0002, atr_slippage_multiplier: float = 0.1):
        """
        Initializes the Broker.

        Args:
            portfolio (Portfolio): A reference to the main portfolio instance.
            data_handler (DataHandler): A reference to the main data handler instance.
            base_slippage_pct (float): A small, fixed component of slippage.
            atr_slippage_multiplier (float): Percentage of ATR to use for dynamic slippage.
        """
        self.portfolio = portfolio
        self.data_handler = data_handler
        self.base_slippage_pct = base_slippage_pct
        self.atr_slippage_multiplier = atr_slippage_multiplier
        logger.info(f"Broker (v1.0 - Precision Execution) initialized.")

    def execute_order(self, order: Dict[str, Any], current_timestamp: pd.Timestamp):
        """
        Executes a given order against the historical data, adhering to strict
        no-look-ahead-bias rules.

        Args:
            order (Dict[str, Any]): The order event from the Portfolio.
                                    Contract: {'timestamp', 'symbol', 'direction', 'quantity', 'order_type'}
            current_timestamp (pd.Timestamp): The timestamp of the candle THAT GENERATED the signal (Candle T).
        """
        symbol = order['symbol']
        timeframe = order['timeframe'] # Assuming timeframe is passed in the order
        
        # Load the full historical data for the symbol
        full_data = self.data_handler.load_data(symbol, timeframe)
        if full_data is None:
            logger.error(f"Broker: Could not load data for {symbol}@{timeframe} to execute order.")
            return

        try:
            # ✅ UPGRADE 1: Look-Ahead Bias Prevention
            # Find the index of the signal candle (T)
            signal_candle_index = full_data.index.get_loc(current_timestamp)
            
            # Check if there is a next candle (T+1)
            if signal_candle_index + 1 >= len(full_data):
                logger.warning(f"Order for {symbol} at {current_timestamp} cannot be filled. End of data series.")
                return

            # Execute at the open price of the next candle (T+1)
            execution_candle = full_data.iloc[signal_candle_index + 1]
            fill_price = execution_candle['open']
            execution_timestamp = execution_candle.name

        except KeyError:
            logger.error(f"Broker: Timestamp {current_timestamp} not found in data for {symbol}@{timeframe}.")
            return
        
        # ✅ UPGRADE 2: Realistic Slippage Model
        # Slippage = (Base % of price) + (Randomized % of ATR of signal candle)
        signal_candle = full_data.loc[current_timestamp]
        # Note: Assumes a standard ATR column exists. This can be made more robust later if needed.
        atr_col = next((col for col in full_data.columns if 'atr_' in col), None)
        
        base_slippage = fill_price * self.base_slippage_pct
        dynamic_slippage = 0.0
        if atr_col and atr_col in signal_candle and pd.notna(signal_candle[atr_col]):
            dynamic_slippage = (signal_candle[atr_col] * self.atr_slippage_multiplier) * random.uniform(0.5, 1.5)
        
        total_slippage = base_slippage + dynamic_slippage
        
        if order['direction'] == 'BUY':
            fill_price += total_slippage
        else: # SELL
            fill_price -= total_slippage
            
        # --- Standard Execution Logic ---
        quantity = order['quantity']
        commission = (quantity * fill_price) * (self.portfolio.commission_pct / 100.0)

        logger.info(f"Executing order: {order['direction']} {quantity:.4f} {symbol} "
                    f"@ market. Fill Price (incl. slippage): ${fill_price:.5f}")

        # ✅ UPGRADE 3: Anti-Fragile Fill Event Contract
        fill_event = {
            'timestamp': execution_timestamp,
            'symbol': symbol,
            'direction': order['direction'],
            'quantity': quantity,
            'fill_price': fill_price,
            'commission': commission
        }

        # Send the execution report back to the Portfolio
        self.portfolio.on_fill(fill_event)

