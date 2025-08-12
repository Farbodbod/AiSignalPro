import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Tuple, Optional

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class ZigzagIndicator(BaseIndicator):
    """
    ZigZag Indicator - (v5.0 - Harmonized API)
    -------------------------------------------------------------------------------
    This world-class version introduces standardized static methods (`get_pivots_col_name`,
    `get_prices_col_name`) to create a robust and unbreakable contract with all
    dependent indicators (like Structure, Divergence, Fibonacci) within the

    Multi-Version Engine.
    """
    dependencies: list = []

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.deviation = float(self.params.get('deviation', 3.0))
        self.timeframe = self.params.get('timeframe', None)

        # ✅ HARMONIZED: Column names are now generated using the official static methods
        self.col_pivots = ZigzagIndicator.get_pivots_col_name(self.params, self.timeframe)
        self.col_prices = ZigzagIndicator.get_prices_col_name(self.params, self.timeframe)

    @staticmethod
    def get_pivots_col_name(params: Dict[str, Any], timeframe: Optional[str] = None) -> str:
        """ ✅ NEW: The official, standardized method for generating the pivots column name. """
        deviation = params.get('deviation', 3.0)
        name = f'zigzag_pivots_{deviation}'
        if timeframe: name += f'_{timeframe}'
        return name

    @staticmethod
    def get_prices_col_name(params: Dict[str, Any], timeframe: Optional[str] = None) -> str:
        """ ✅ NEW: The official, standardized method for generating the prices column name. """
        deviation = params.get('deviation', 3.0)
        name = f'zigzag_prices_{deviation}'
        if timeframe: name += f'_{timeframe}'
        return name

    def _get_pivots(self, df: pd.DataFrame, deviation_threshold: float) -> Tuple[np.ndarray, np.ndarray]:
        """The complete, non-repainting pivot detection logic (Unchanged)."""
        highs, lows = df['high'].values, df['low'].values
        pivots, prices = np.zeros(len(df), dtype=int), np.zeros(len(df), dtype=float)
        if len(df) == 0: return pivots, prices

        last_pivot_idx, trend = 0, 0
        last_pivot_price = highs[0]

        for i in range(1, len(df)):
            current_high, current_low = highs[i], lows[i]
            if trend == 0:
                if current_high > last_pivot_price * (1 + deviation_threshold / 100):
                    trend = 1; pivots[last_pivot_idx] = -1; prices[last_pivot_idx] = lows[last_pivot_idx]
                    last_pivot_price, last_pivot_idx = current_high, i
                elif current_low < last_pivot_price * (1 - deviation_threshold / 100):
                    trend = -1; pivots[last_pivot_idx] = 1; prices[last_pivot_idx] = highs[last_pivot_idx]
                    last_pivot_price, last_pivot_idx = current_low, i
            elif trend == 1:
                if current_high > last_pivot_price: last_pivot_price, last_pivot_idx = current_high, i
                elif current_low < last_pivot_price * (1 - deviation_threshold / 100):
                    pivots[last_pivot_idx] = 1; prices[last_pivot_idx] = last_pivot_price
                    trend = -1; last_pivot_price, last_pivot_idx = current_low, i
            elif trend == -1:
                if current_low < last_pivot_price: last_pivot_price, last_pivot_idx = current_low, i
                elif current_high > last_pivot_price * (1 + deviation_threshold / 100):
                    pivots[last_pivot_idx] = -1; prices[last_pivot_idx] = last_pivot_price
                    trend = 1; last_pivot_price, last_pivot_idx = current_high, i
        return pivots, prices

    def calculate(self) -> 'ZigzagIndicator':
        """ Core calculation logic is unchanged and robust. """
        df_for_calc = self.df
        if len(df_for_calc) < 3:
            logger.warning(f"Not enough data for ZigZag on {self.timeframe or 'base'}")
            self.df[self.col_pivots] = 0
            self.df[self.col_prices] = 0.0
            return self

        pivots, prices = self._get_pivots(df_for_calc, self.deviation)
        self.df[self.col_pivots] = pivots
        self.df[self.col_prices] = prices
        return self

    def analyze(self) -> dict:
        """ Analysis logic is unchanged and robust. """
        required_cols = [self.col_pivots, self.col_prices]
        valid_df = self.df.dropna(subset=required_cols)
        pivots_df = valid_df[valid_df[self.col_pivots] != 0]
        
        if len(pivots_df) < 2:
            return {"status": "Awaiting Pivots"}

        last_pivot = pivots_df.iloc[-1]
        prev_pivot = pivots_df.iloc[-2]
        last_type = 'peak' if last_pivot[self.col_pivots] == 1 else 'trough'
        last_price = last_pivot[self.col_prices]

        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "analysis": {
                "last_pivot": {"type": last_type, "price": round(last_price, 5), "time": last_pivot.name.strftime('%Y-%m-%d %H:%M:%S')},
                "previous_pivot": {"type": 'peak' if prev_pivot[self.col_pivots] == 1 else 'trough', "price": round(prev_pivot[self.col_prices], 5), "time": prev_pivot.name.strftime('%Y-%m-%d %H:%M:%S')},
                "signal": "bullish" if last_type == 'trough' else "bearish"
            }
        }
