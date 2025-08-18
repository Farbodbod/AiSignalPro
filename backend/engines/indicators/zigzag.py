# backend/engines/indicators/zigzag.py
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Tuple

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class ZigzagIndicator(BaseIndicator):
    """
    ZigZag Indicator - (v6.0 - DI Native & Cleaned Architecture)
    -------------------------------------------------------------------------------
    This world-class version has been refactored to align with the Dependency
    Injection architecture. The obsolete static methods (`get_..._col_name`) have 
    been removed to finalize the cleanup of all data provider indicators. The core,
    non-repainting pivot detection algorithm remains 100% intact.
    """
    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], dependencies: Dict[str, BaseIndicator], **kwargs):
        super().__init__(df, params=params, dependencies=dependencies, **kwargs)
        self.deviation = float(self.params.get('deviation', 3.0))
        self.timeframe = self.params.get('timeframe')

        # Simplified, robust, and locally-scoped column names for consumers to find
        self.pivots_col = 'PIVOTS'
        self.prices_col = 'PRICES'

    def _get_pivots(self, df: pd.DataFrame, deviation_threshold: float) -> Tuple[np.ndarray, np.ndarray]:
        """
        The core, non-repainting pivot detection logic.
        This algorithm is 100% preserved from the previous version.
        """
        highs, lows = df['high'].values, df['low'].values
        pivots, prices = np.zeros(len(df), dtype=int), np.zeros(len(df), dtype=float)
        if len(df) == 0: return pivots, prices

        last_pivot_idx, trend = 0, 0
        # Initialize with the first price point
        last_pivot_price = highs[0] if highs[0] > df['open'].iloc[0] else lows[0]

        for i in range(1, len(df)):
            current_high, current_low = highs[i], lows[i]
            if trend == 0:
                if current_high > last_pivot_price * (1 + deviation_threshold / 100):
                    trend = 1; pivots[last_pivot_idx] = -1; prices[last_pivot_idx] = lows[last_pivot_idx]
                    last_pivot_price, last_pivot_idx = current_high, i
                elif current_low < last_pivot_price * (1 - deviation_threshold / 100):
                    trend = -1; pivots[last_pivot_idx] = 1; prices[last_pivot_idx] = highs[last_pivot_idx]
                    last_pivot_price, last_pivot_idx = current_low, i
            elif trend == 1: # Uptrend, looking for a peak
                if current_high > last_pivot_price: last_pivot_price, last_pivot_idx = current_high, i
                elif current_low < last_pivot_price * (1 - deviation_threshold / 100):
                    pivots[last_pivot_idx] = 1; prices[last_pivot_idx] = last_pivot_price
                    trend = -1; last_pivot_price, last_pivot_idx = current_low, i
            elif trend == -1: # Downtrend, looking for a trough
                if current_low < last_pivot_price: last_pivot_price, last_pivot_idx = current_low, i
                elif current_high > last_pivot_price * (1 + deviation_threshold / 100):
                    pivots[last_pivot_idx] = -1; prices[last_pivot_idx] = last_pivot_price
                    trend = 1; last_pivot_price, last_pivot_idx = current_high, i
        return pivots, prices

    def calculate(self) -> 'ZigzagIndicator':
        """ Core calculation logic is unchanged and robust. """
        if len(self.df) < 3:
            logger.warning(f"Not enough data for ZigZag on {self.timeframe or 'base'}")
            self.df[self.pivots_col] = 0
            self.df[self.prices_col] = 0.0
            return self

        pivots, prices = self._get_pivots(self.df, self.deviation)
        self.df[self.pivots_col] = pivots
        self.df[self.prices_col] = prices
        return self

    def analyze(self) -> dict:
        """ Analysis logic is unchanged and robust. """
        required_cols = [self.pivots_col, self.prices_col]
        valid_df = self.df.dropna(subset=required_cols)
        pivots_df = valid_df[valid_df[self.pivots_col] != 0]
        
        if len(pivots_df) < 2:
            return {"status": "Awaiting Pivots"}

        last_pivot = pivots_df.iloc[-1]
        prev_pivot = pivots_df.iloc[-2]
        last_type = 'peak' if last_pivot[self.pivots_col] == 1 else 'trough'
        last_price = last_pivot[self.prices_col]

        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "analysis": {
                "last_pivot": {"type": last_type, "price": round(last_price, 5), "time": last_pivot.name.strftime('%Y-%m-%d %H:%M:%S')},
                "previous_pivot": {"type": 'peak' if prev_pivot[self.pivots_col] == 1 else 'trough', "price": round(prev_pivot[self.prices_col], 5), "time": prev_pivot.name.strftime('%Y-%m-%d %H:%M:%S')},
                "signal": "bullish" if last_type == 'trough' else "bearish"
            }
        }
