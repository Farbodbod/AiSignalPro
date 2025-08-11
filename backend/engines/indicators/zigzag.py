import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Tuple

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class ZigzagIndicator(BaseIndicator):
    """
    ZigZag Indicator - Definitive, World-Class Version (v4.1 - Final Architecture)
    -------------------------------------------------------------------------------
    This version adheres to the final AiSignalPro architecture. It performs its
    complex, non-repainting calculations on the pre-resampled dataframe provided
    by the IndicatorAnalyzer. Its analysis is hardened to be fully bias-free.
    """
    dependencies: list = []

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.deviation = float(self.params.get('deviation', 3.0))
        self.timeframe = self.params.get('timeframe', None)

        suffix = f'_{self.deviation}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.col_pivots = f'zigzag_pivots{suffix}'
        self.col_prices = f'zigzag_prices{suffix}'

    def _validate_input(self, df: pd.DataFrame) -> pd.DataFrame:
        """Validates the input DataFrame."""
        required_cols = {'high', 'low', 'close'}
        if not required_cols.issubset(df.columns):
            missing = required_cols - set(df.columns)
            raise ValueError(f"Missing required columns for ZigZag: {missing}")
        
        if len(df) < 3:
            logger.warning("ZigZag calculation may be unreliable: data length < 3.")

        for col in required_cols:
             if not pd.api.types.is_numeric_dtype(df[col]):
                  df[col] = pd.to_numeric(df[col], errors='coerce')
        return df.dropna(subset=required_cols)

    def _get_pivots(self, df: pd.DataFrame, deviation_threshold: float) -> Tuple[np.ndarray, np.ndarray]:
        """The complete, non-repainting pivot detection logic."""
        highs = df['high'].values
        lows = df['low'].values
        pivots = np.zeros(len(df), dtype=int)
        prices = np.zeros(len(df), dtype=float)
        
        if len(df) == 0:
            return pivots, prices

        last_pivot_idx = 0
        last_pivot_price = highs[0]
        trend = 0  # 0 = undecided, 1 = uptrend, -1 = downtrend

        for i in range(1, len(df)):
            current_high, current_low = highs[i], lows[i]
            if trend == 0:
                if current_high > last_pivot_price * (1 + deviation_threshold / 100):
                    trend = 1
                    pivots[last_pivot_idx] = -1  # The last pivot was a trough
                    prices[last_pivot_idx] = lows[last_pivot_idx]
                    last_pivot_price = current_high
                    last_pivot_idx = i
                elif current_low < last_pivot_price * (1 - deviation_threshold / 100):
                    trend = -1
                    pivots[last_pivot_idx] = 1  # The last pivot was a peak
                    prices[last_pivot_idx] = highs[last_pivot_idx]
                    last_pivot_price = current_low
                    last_pivot_idx = i
            elif trend == 1:  # In an uptrend, looking for a peak
                if current_high > last_pivot_price:
                    last_pivot_price = current_high
                    last_pivot_idx = i
                elif current_low < last_pivot_price * (1 - deviation_threshold / 100):
                    pivots[last_pivot_idx] = 1  # Confirmed the peak
                    prices[last_pivot_idx] = last_pivot_price
                    trend = -1
                    last_pivot_price = current_low
                    last_pivot_idx = i
            elif trend == -1:  # In a downtrend, looking for a trough
                if current_low < last_pivot_price:
                    last_pivot_price = current_low
                    last_pivot_idx = i
                elif current_high > last_pivot_price * (1 + deviation_threshold / 100):
                    pivots[last_pivot_idx] = -1  # Confirmed the trough
                    prices[last_pivot_idx] = last_pivot_price
                    trend = 1
                    last_pivot_price = current_high
                    last_pivot_idx = i
        
        return pivots, prices

    def calculate(self) -> 'ZigzagIndicator':
        """ ✨ FINAL ARCHITECTURE: No resampling. Just pure calculation. """
        df_for_calc = self.df
        
        validated_df = self._validate_input(df_for_calc)
        pivots, prices = self._get_pivots(validated_df, self.deviation)
        
        # Assign the results directly to the main dataframe
        self.df[self.col_pivots] = pivots
        self.df[self.col_prices] = prices
        
        return self

    def analyze(self) -> dict:
        """Provides a deep, bias-free analysis of the market structure."""
        required_cols = [self.col_pivots, self.col_prices, 'close']
        valid_df = self.df.dropna(subset=required_cols)
        pivots_df = valid_df[valid_df[self.col_pivots] != 0]
        
        if len(pivots_df) < 2:
            return {"status": "Awaiting Pivots", "timeframe": self.timeframe or 'Base', "analysis": {}}

        if len(self.df) < 2:
            return {"status": "Insufficient Data", "timeframe": self.timeframe or 'Base', "analysis": {}}
            
        current_price = self.df.iloc[-2]['close']

        last_pivot = pivots_df.iloc[-1]
        prev_pivot = pivots_df.iloc[-2]
        last_type = 'peak' if last_pivot[self.col_pivots] == 1 else 'trough'
        last_price = last_pivot[self.col_prices]
        
        bos_signal = 'None'
        if last_type == 'peak' and current_price > last_price:
            bos_signal = 'Bullish BOS'
        elif last_type == 'trough' and current_price < last_price:
            bos_signal = 'Bearish BOS'

        def to_safe_json(value):
            if hasattr(value, 'strftime'): return value.strftime('%Y-%m-%d %H:%M:%S')
            return str(value)

        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "analysis": {
                "last_pivot": {"type": last_type, "price": round(last_price, 5), "time": to_safe_json(last_pivot.name)},
                "previous_pivot": {"type": 'peak' if prev_pivot[self.col_pivots] == 1 else 'trough', "price": round(prev_pivot[self.col_prices], 5), "time": to_safe_json(prev_pivot.name)},
                "market_structure_signal": bos_signal,
                "signal": "bullish" if last_type == 'trough' else "bearish"
            }
        }
