# backend/engines/indicators/zigzag.py (v8.0 - The Anti-Repaint Edition)
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Tuple, Optional

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class ZigzagIndicator(BaseIndicator):
    """
    ZigZag Indicator - (v8.0 - The Anti-Repaint Edition)
    -------------------------------------------------------------------------------
    This world-class version solves the critical "repainting" problem by
    introducing Pivot Confirmation Logic. The analyze() method now distinguishes
    between the 'last_confirmed_pivot' and the 'candidate_pivot', providing
    downstream consumers (like Fibonacci and Structure) with a 100% reliable,
    non-repainting foundation for market structure analysis.
    """
    dependencies: list = []

    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], **kwargs):
        super().__init__(df, params=params, **kwargs)
        self.deviation = float(self.params.get('deviation', 3.0))
        self.timeframe = self.params.get('timeframe')
        self.pivots_col = 'PIVOTS'
        self.prices_col = 'PRICES'

    def _get_pivots(self, df: pd.DataFrame, deviation_threshold: float) -> Tuple[np.ndarray, np.ndarray]:
        # The core pivot detection algorithm is preserved and robust.
        highs, lows = df['high'].values, df['low'].values
        pivots, prices = np.zeros(len(df), dtype=int), np.zeros(len(df), dtype=float)
        if len(df) < 3: return pivots, prices

        last_pivot_idx, trend = 0, 0
        
        # Improved initialization: Find the first real move.
        for i in range(1, len(df)):
            if highs[i] > highs[0] * (1 + deviation_threshold / 100):
                trend = 1; last_pivot_price, last_pivot_idx = highs[i], i
                pivots[0] = -1; prices[0] = lows[0]
                break
            elif lows[i] < lows[0] * (1 - deviation_threshold / 100):
                trend = -1; last_pivot_price, last_pivot_idx = lows[i], i
                pivots[0] = 1; prices[0] = highs[0]
                break
        
        if trend == 0: return pivots, prices

        for i in range(last_pivot_idx + 1, len(df)):
            current_high, current_low = highs[i], lows[i]
            if trend == 1: # Uptrend, looking for a peak
                if current_high >= last_pivot_price:
                    last_pivot_price, last_pivot_idx = current_high, i
                elif current_low < last_pivot_price * (1 - deviation_threshold / 100):
                    pivots[last_pivot_idx] = 1; prices[last_pivot_idx] = last_pivot_price
                    trend = -1; last_pivot_price, last_pivot_idx = current_low, i
            elif trend == -1: # Downtrend, looking for a trough
                if current_low <= last_pivot_price:
                    last_pivot_price, last_pivot_idx = current_low, i
                elif current_high > last_pivot_price * (1 + deviation_threshold / 100):
                    pivots[last_pivot_idx] = -1; prices[last_pivot_idx] = last_pivot_price
                    trend = 1; last_pivot_price, last_pivot_idx = current_high, i
        
        # Set the final candidate pivot
        if trend != 0:
            pivots[last_pivot_idx] = trend
            prices[last_pivot_idx] = last_pivot_price

        return pivots, prices

    def calculate(self) -> 'ZigzagIndicator':
        if len(self.df) < 3:
            logger.warning(f"Not enough data for ZigZag on {self.timeframe or 'base'}")
            self.df[self.pivots_col] = 0; self.df[self.prices_col] = 0.0
            return self
        pivots, prices = self._get_pivots(self.df, self.deviation)
        self.df[self.pivots_col] = pivots; self.df[self.prices_col] = prices
        return self

    def _format_pivot_data(self, pivot_series: pd.Series) -> Dict:
        """Helper to format a pivot point into a clean dictionary."""
        pivot_type = 'peak' if pivot_series[self.pivots_col] == 1 else 'trough'
        return {
            "type": pivot_type,
            "price": round(pivot_series[self.prices_col], 5),
            "time": pivot_series.name.strftime('%Y-%m-%d %H:%M:%S')
        }

    def analyze(self) -> dict:
        pivots_df = self.df[self.df[self.pivots_col] != 0]
        
        # If not even one pivot is found, there is no structure yet.
        if len(pivots_df) < 1:
            return {"status": "Awaiting Pivots", "values": {}, "analysis": {}}

        # The last pivot is always the unconfirmed "candidate".
        candidate_pivot = self._format_pivot_data(pivots_df.iloc[-1])
        last_confirmed_pivot: Optional[Dict] = None
        previous_confirmed_pivot: Optional[Dict] = None
        swing_trend = "Unknown"

        # You need at least 2 pivots to have one confirmed pivot.
        if len(pivots_df) >= 2:
            last_confirmed_pivot = self._format_pivot_data(pivots_df.iloc[-2])
        
        # You need at least 3 pivots to define the last completed swing.
        if len(pivots_df) >= 3:
            previous_confirmed_pivot = self._format_pivot_data(pivots_df.iloc[-3])
            # Define swing trend based on the last TWO CONFIRMED pivots
            if last_confirmed_pivot['type'] == 'peak' and previous_confirmed_pivot['type'] == 'trough':
                swing_trend = "Up" if last_confirmed_pivot['price'] > previous_confirmed_pivot['price'] else "Down"
            elif last_confirmed_pivot['type'] == 'trough' and previous_confirmed_pivot['type'] == 'peak':
                swing_trend = "Down" if last_confirmed_pivot['price'] < previous_confirmed_pivot['price'] else "Up"

        analysis_content = {
            "last_confirmed_pivot": last_confirmed_pivot,
            "candidate_pivot": candidate_pivot,
            "previous_confirmed_pivot": previous_confirmed_pivot,
            "swing_trend": swing_trend, # This is the reliable trend for Fibonacci
            "signal": "bullish" if candidate_pivot['type'] == 'trough' else "bearish"
        }
        
        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "values": analysis_content,
            "analysis": analysis_content # For backward compatibility
        }
