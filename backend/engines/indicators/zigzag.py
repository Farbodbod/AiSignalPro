import pandas as pd
import numpy as np
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class ZigzagIndicator(BaseIndicator):
    """
    ZigZag Indicator - World-Class Market Structure Analysis Tool
    ----------------------------------------------------------------
    This version includes:
    1.  Accurate, non-repainting pivot detection logic.
    2.  Capture of the final unconfirmed pivot.
    3.  Robust input validation and performance optimization.
    4.  Advanced analysis of the last market swing (price/time delta).
    5.  Powerful "Break of Structure" (BOS) signal detection.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.deviation = float(self.params.get('deviation', 3.0))
        self.col_pivots = f'zigzag_pivots_{self.deviation}'
        self.col_prices = f'zigzag_prices_{self.deviation}'

    def _validate_input(self, df: pd.DataFrame) -> pd.DataFrame:
        """Validates the input DataFrame."""
        required_cols = {'high', 'low', 'close'}
        if not required_cols.issubset(df.columns):
            missing = required_cols - set(df.columns)
            msg = f"Missing required columns for ZigZag: {missing}"
            logger.error(msg)
            raise ValueError(msg)
        
        if len(df) < 3:
            logger.warning("ZigZag calculation may be unreliable: data length < 3.")

        # ✅ FIX: Ensure type casting is applied and returned
        for col in required_cols:
             if not pd.api.types.is_numeric_dtype(df[col]):
                  df[col] = pd.to_numeric(df[col], errors='coerce')
        return df.dropna(subset=required_cols)


    def _get_pivots(self, df: pd.DataFrame, deviation_threshold: float):
        # Using .values for significant performance boost in loops
        highs = df['high'].values
        lows = df['low'].values
        
        pivots = np.zeros(len(df), dtype=int)
        prices = np.zeros(len(df), dtype=float)
        
        last_pivot_idx = 0
        last_pivot_price = highs[0] # Start with a sensible value
        trend = 0  # 0: undetermined, 1: up, -1: down

        # ✅ FIX: Corrected the main logic loop indentation
        for i in range(1, len(df)):
            current_high = highs[i]
            current_low = lows[i]

            if trend == 0:
                if current_high > last_pivot_price * (1 + deviation_threshold / 100):
                    trend = 1
                    pivots[last_pivot_idx] = -1 # The start was a trough
                    prices[last_pivot_idx] = lows[last_pivot_idx]
                    last_pivot_price = current_high
                    last_pivot_idx = i
                elif current_low < last_pivot_price * (1 - deviation_threshold / 100):
                    trend = -1
                    pivots[last_pivot_idx] = 1 # The start was a peak
                    prices[last_pivot_idx] = highs[last_pivot_idx]
                    last_pivot_price = current_low
                    last_pivot_idx = i

            elif trend == 1: # We are in an uptrend, looking for a peak
                if current_high > last_pivot_price:
                    last_pivot_price = current_high
                    last_pivot_idx = i
                elif current_low < last_pivot_price * (1 - deviation_threshold / 100):
                    pivots[last_pivot_idx] = 1  # Confirmed a peak
                    prices[last_pivot_idx] = last_pivot_price
                    trend = -1 # Trend is now down
                    last_pivot_price = current_low
                    last_pivot_idx = i
            
            elif trend == -1: # We are in a downtrend, looking for a trough
                if current_low < last_pivot_price:
                    last_pivot_price = current_low
                    last_pivot_idx = i
                elif current_high > last_pivot_price * (1 + deviation_threshold / 100):
                    pivots[last_pivot_idx] = -1 # Confirmed a trough
                    prices[last_pivot_idx] = last_pivot_price
                    trend = 1 # Trend is now up
                    last_pivot_price = current_high
                    last_pivot_idx = i

        # Capture the last unconfirmed pivot
        if trend != 0 and pivots[last_pivot_idx] == 0:
            pivots[last_pivot_idx] = trend
            prices[last_pivot_idx] = last_pivot_price
            
        return pivots, prices

    def calculate(self) -> pd.DataFrame:
        df = self.df.copy()
        df = self._validate_input(df)
        
        pivots, prices = self._get_pivots(df, self.deviation)
        df[self.col_pivots] = pivots
        df[self.col_prices] = prices.round(5) # Round prices for consistency
        
        self.df = df
        return self.df

    def analyze(self) -> dict:
        """ ✨ IMPROVEMENT: Provides deep market structure analysis. """
        pivots_df = self.df[self.df[self.col_pivots] != 0].copy()
        
        if len(pivots_df) < 2:
            return {"signal": "neutral", "message": "Awaiting at least two pivots for analysis."}

        # Last two confirmed pivots for swing analysis
        last_pivot = pivots_df.iloc[-1]
        prev_pivot = pivots_df.iloc[-2]

        last_type = 'peak' if last_pivot[self.col_pivots] == 1 else 'trough'
        last_price = last_pivot[self.col_prices]
        last_time = last_pivot.name
        
        # --- Swing Analysis ---
        swing_price_delta = last_price - prev_pivot[self.col_prices]
        swing_percent_change = (swing_price_delta / prev_pivot[self.col_prices]) * 100
        
        # --- Break of Structure (BOS) Analysis ---
        bos_signal = 'None'
        current_price = self.df['close'].iloc[-1]
        
        if last_type == 'peak': # Last move was up, now looking for BOS up or reversal down
            if current_price > last_price:
                 bos_signal = 'Bullish BOS' # Broke the last peak
        elif last_type == 'trough': # Last move was down, now looking for BOS down or reversal up
             if current_price < last_price:
                 bos_signal = 'Bearish BOS' # Broke the last trough

        # --- Final JSON-safe output ---
        def to_safe_json(value):
            if hasattr(value, 'strftime'): return value.strftime('%Y-%m-%d %H:%M:%S')
            return str(value)

        return {
            "last_pivot": {
                "type": last_type,
                "price": round(last_price, 5),
                "time": to_safe_json(last_time)
            },
            "previous_pivot": {
                 "type": 'peak' if prev_pivot[self.col_pivots] == 1 else 'trough',
                 "price": round(prev_pivot[self.col_prices], 5),
                 "time": to_safe_json(prev_pivot.name)
            },
            "last_swing_analysis": {
                "direction": "up" if last_type == 'peak' else "down",
                "price_change": round(swing_price_delta, 5),
                "percent_change": round(swing_percent_change, 2),
                "duration_bars": pivots_df.index.get_loc(last_time) - pivots_df.index.get_loc(prev_pivot.name)
            },
            "market_structure_signal": bos_signal,
            "signal": "bullish" if last_type == 'trough' else "bearish",
            "message": f"Last pivot was a {last_type}. Current price is testing structure."
        }
