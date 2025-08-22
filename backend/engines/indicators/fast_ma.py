# backend/engines/indicators/fast_ma.py (v6.1 - The Grandmaster Flow Edition)

import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Optional

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class FastMAIndicator(BaseIndicator):
    """
    Fast MA (DEMA/TEMA) - (v6.1 - The Grandmaster Flow Edition)
    ----------------------------------------------------------------------------------
    This world-class version perfects the "Smoothed Flow" analysis by applying
    smoothing to acceleration as well as slope. It also introduces a configurable
    smoothing period and enriches the final analysis output, achieving the pinnacle
    of robustness, flexibility, and analytical depth for this indicator.
    """
    dependencies: list = []

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.period = int(self.params.get('period', 200))
        self.ma_type = str(self.params.get('ma_type', 'DEMA')).upper()
        self.timeframe = self.params.get('timeframe', None)
        self.slope_threshold = float(self.params.get('slope_threshold', 0.0005))
        # ✅ FULLY CONFIGURABLE: Smoothing period is now a tunable parameter.
        self.slope_smoothing_period = int(self.params.get('slope_smoothing_period', 3))

        if self.period < 1: raise ValueError("Period must be a positive integer.")
        if self.ma_type not in ['DEMA', 'TEMA']: raise ValueError("ma_type must be 'DEMA' or 'TEMA'.")
        
        suffix = f'_{self.period}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        else: suffix += '_base'
        self.ma_col = f'{self.ma_type.lower()}{suffix}'
        self.slope_col = f'{self.ma_col}_slope'
        self.accel_col = f'{self.ma_col}_accel'

    def calculate(self) -> 'FastMAIndicator':
        if len(self.df) < self.period * 2:
            logger.warning(f"Not enough data for {self.ma_type} on {self.timeframe or 'base'}.")
            for col in [self.ma_col, self.slope_col, self.accel_col]: self.df[col] = np.nan
            return self

        close_series = pd.to_numeric(self.df['close'], errors='coerce')
        
        ema1 = close_series.ewm(span=self.period, adjust=False).mean()
        ema2 = ema1.ewm(span=self.period, adjust=False).mean()
        
        if self.ma_type == 'DEMA':
            ma_series = 2 * ema1 - ema2
        else: # TEMA
            ema3 = ema2.ewm(span=self.period, adjust=False).mean()
            ma_series = 3 * ema1 - 3 * ema2 + ema3
        
        self.df[self.ma_col] = ma_series

        # ✅ GRANDMASTER FLOW: Apply smoothing to both slope and acceleration for maximum noise reduction.
        slope_series = ma_series.diff().ewm(span=self.slope_smoothing_period, adjust=False).mean()
        self.df[self.slope_col] = slope_series
        self.df[self.accel_col] = slope_series.diff().ewm(span=self.slope_smoothing_period, adjust=False).mean()
        
        return self

    def analyze(self) -> Dict[str, Any]:
        required_cols = [self.ma_col, self.slope_col, self.accel_col, 'close']
        empty_analysis = {"values": {}, "analysis": {}}

        if not all(col in self.df.columns for col in required_cols):
            return {"status": "Calculation Incomplete", **empty_analysis}
            
        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 1:
            return {"status": "Insufficient Data", **empty_analysis}

        last = valid_df.iloc[-1]
        close_price, ma_val, slope, acceleration = last['close'], last[self.ma_col], last[self.slope_col], last[self.accel_col]
        
        signal, message, strength = "Neutral", "No clear momentum signal.", "Neutral"
        
        min_threshold = 1e-9
        normalized_slope_threshold = max(abs(ma_val) * self.slope_threshold, min_threshold)
        
        is_bullish = close_price > ma_val and slope > normalized_slope_threshold
        is_bearish = close_price < ma_val and slope < -normalized_slope_threshold

        if is_bullish:
            signal = "Buy"
            strength = "Accelerating" if acceleration > 0 else "Decelerating"
            message = f"Bullish trend ({strength}). Price is above {self.ma_type} and slope is positive."
        elif is_bearish:
            signal = "Sell"
            strength = "Accelerating" if acceleration < 0 else "Decelerating"
            message = f"Bearish trend ({strength}). Price is below {self.ma_type} and slope is negative."
            
        values_content = { "ma_value": round(ma_val, 5), "price": round(close_price, 5) }
        # ✅ RICHER OUTPUT: The 'strength' field is now correctly included in the analysis.
        analysis_content = { "signal": signal, "strength": strength, "slope": round(slope, 5), "acceleration": round(acceleration, 5), "message": message }

        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "indicator_type": self.ma_type,
            "values": values_content,
            "analysis": analysis_content
        }
