import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class BollingerIndicator(BaseIndicator):
    """
    Bollinger Bands - (v5.0 - Miracle Edition)
    -----------------------------------------------------------------------------
    This world-class version is a true adaptive analysis engine. It features:
    1.  Adaptive Squeeze Engine: Dynamically calculates the squeeze threshold
        based on the asset's historical volatility, eliminating fixed numbers.
    2.  Multi-State Signal Engine: Identifies and reports specific, actionable
        events like "Squeeze Release Bullish/Bearish" for high-precision strategies.
    3.  Harmonized Architecture: Built to perform flawlessly within AiSignalPro's
        multi-timeframe, specialist-per-timeframe architecture.
    """
    dependencies: list = []

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.period = int(self.params.get('period', 20))
        self.std_dev = float(self.params.get('std_dev', 2.0))
        self.timeframe = self.params.get('timeframe', None)
        # ✅ NEW: Parameters for the Adaptive Squeeze Engine
        self.squeeze_lookback = int(self.params.get('squeeze_lookback', 120))
        self.squeeze_stats_period = int(self.params.get('squeeze_stats_period', 240)) # Lookback for calculating mean/std of width
        self.squeeze_std_multiplier = float(self.params.get('squeeze_std_multiplier', 1.5)) # How many std devs below the mean defines a squeeze

        suffix = f'_{self.period}_{self.std_dev}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.middle_col = f'bb_middle{suffix}'
        self.upper_col = f'bb_upper{suffix}'
        self.lower_col = f'bb_lower{suffix}'
        self.width_col = f'bb_width{suffix}'
        self.percent_b_col = f'bb_percent_b{suffix}'

    def calculate(self) -> 'BollingerIndicator':
        """ Core calculation logic remains the same. """
        df_for_calc = self.df
        
        if len(df_for_calc) < self.period:
            logger.warning(f"Not enough data for Bollinger Bands on timeframe {self.timeframe or 'base'}.")
            for col in [self.middle_col, self.upper_col, self.lower_col, self.width_col, self.percent_b_col]:
                self.df[col] = np.nan
            return self

        middle = df_for_calc['close'].rolling(window=self.period).mean()
        std = df_for_calc['close'].rolling(window=self.period).std(ddof=0)
        
        upper = middle + (std * self.std_dev)
        lower = middle - (std * self.std_dev)
        
        safe_middle = middle.replace(0, np.nan)
        # The width is already normalized by dividing by the middle band.
        width = (upper - lower) / safe_middle * 100
        percent_b = (df_for_calc['close'] - lower) / (upper - lower).replace(0, np.nan)
        
        self.df[self.middle_col] = middle
        self.df[self.upper_col] = upper
        self.df[self.lower_col] = lower
        self.df[self.width_col] = width
        self.df[self.percent_b_col] = percent_b
            
        return self

    def analyze(self) -> Dict[str, Any]:
        """
        The new, adaptive analysis engine with multi-state signal detection.
        """
        required_cols = [self.middle_col, self.width_col, self.percent_b_col]
        # We need a longer history for statistical calculations
        if len(self.df.dropna(subset=required_cols)) < self.squeeze_stats_period:
            return {"status": "Insufficient Data for Squeeze Analysis", "analysis": {}}

        valid_df = self.df.dropna(subset=required_cols)
        last = valid_df.iloc[-1]
        prev = valid_df.iloc[-2]
        
        # --- ✅ 1. Adaptive Squeeze Engine ---
        # Calculate statistics over a long lookback period
        width_history = valid_df[self.width_col].tail(self.squeeze_stats_period)
        width_mean = width_history.mean()
        width_std = width_history.std()
        
        # The threshold is now dynamic, not a fixed number!
        dynamic_squeeze_threshold = width_mean - (width_std * self.squeeze_std_multiplier)
        
        is_squeeze_now = last[self.width_col] <= dynamic_squeeze_threshold
        is_squeeze_prev = prev[self.width_col] <= dynamic_squeeze_threshold
        is_squeeze_release = is_squeeze_prev and not is_squeeze_now
        
        # --- ✅ 2. Multi-State Signal Engine ---
        position = "Inside Bands"
        if last[self.percent_b_col] > 1.0: position = "Breakout Above"
        elif last[self.percent_b_col] < 0.0: position = "Breakdown Below"

        trade_signal = "Hold"
        if is_squeeze_release:
            # Check the direction of the breakout candle
            if last['close'] > last['open']:
                trade_signal = "Squeeze Release Bullish"
            else:
                trade_signal = "Squeeze Release Bearish"
        elif is_squeeze_now:
            trade_signal = "Squeeze Active"
        elif position != "Inside Bands":
            trade_signal = position # "Breakout Above" or "Breakdown Below"
        
        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "values": {
                "upper_band": round(last[self.upper_col], 5),
                "middle_band": round(last[self.middle_col], 5),
                "lower_band": round(last[self.lower_col], 5),
                "bandwidth_percent": round(last[self.width_col], 4),
                "percent_b": round(last[self.percent_b_col], 3),
            },
            "analysis": {
                "trade_signal": trade_signal, # The new, powerful data point
                "is_in_squeeze": is_squeeze_now,
                "is_squeeze_release": is_squeeze_release,
                "position": position,
                "dynamic_squeeze_threshold": round(dynamic_squeeze_threshold, 4) # For debugging and insight
            }
        }
