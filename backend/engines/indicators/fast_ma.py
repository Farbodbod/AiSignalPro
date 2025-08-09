import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

# اطمینان حاصل کنید که این اندیکاتور از فایل مربوطه وارد شده‌ است
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class FastMAIndicator(BaseIndicator):
    """
    Fast MA (DEMA/TEMA) - Definitive, MTF, and Advanced Momentum Analysis Version
    -----------------------------------------------------------------------------
    This version provides a world-class implementation of DEMA and TEMA, featuring:
    - The standard AiSignalPro MTF architecture.
    - Advanced momentum analysis, including trend slope and acceleration.
    - A configurable slope threshold to filter out market noise.
    - Robust parameter validation and bias-free analysis.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        # --- Parameter Validation and Setup ---
        self.params = kwargs.get('params', {})
        self.period = int(self.params.get('period', 14))
        self.ma_type = str(self.params.get('ma_type', 'DEMA')).upper()
        self.timeframe = self.params.get('timeframe', None)
        self.slope_threshold = float(self.params.get('slope_threshold', 0.0005)) # 0.05% change threshold

        if self.period < 1: raise ValueError("Period must be a positive integer.")
        if self.ma_type not in ['DEMA', 'TEMA']: raise ValueError("ma_type must be 'DEMA' or 'TEMA'.")
        
        # --- Dynamic Column Naming ---
        suffix = f'_{self.period}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.ma_col = f'{self.ma_type.lower()}{suffix}'

    def _calculate_fast_ma(self, df: pd.DataFrame) -> pd.DataFrame:
        """The core, technically correct DEMA/TEMA calculation logic."""
        res = pd.DataFrame(index=df.index)
        close_series = pd.to_numeric(df['close'], errors='coerce')
        
        ema1 = close_series.ewm(span=self.period, adjust=False).mean()
        ema2 = ema1.ewm(span=self.period, adjust=False).mean()
        
        if self.ma_type == 'DEMA':
            res[self.ma_col] = 2 * ema1 - ema2
        elif self.ma_type == 'TEMA':
            ema3 = ema2.ewm(span=self.period, adjust=False).mean()
            res[self.ma_col] = 3 * ema1 - 3 * ema2 + ema3
            
        return res

    def calculate(self) -> 'FastMAIndicator':
        """Orchestrates the MTF calculation for the Fast Moving Average."""
        base_df = self.df
        
        # ✨ MTF LOGIC: Resample data if a timeframe is specified
        if self.timeframe:
            if not isinstance(base_df.index, pd.DatetimeIndex):
                raise TypeError("DataFrame index must be a DatetimeIndex for MTF.")
            rules = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}
            calc_df = base_df.resample(self.timeframe, label='right', closed='right').apply(rules).dropna()
        else:
            calc_df = base_df.copy()

        if len(calc_df) < self.period * 3: # A safe margin for TEMA
            logger.warning(f"Not enough data for {self.ma_type} on timeframe {self.timeframe or 'base'}.")
            return self

        ma_results = self._calculate_fast_ma(calc_df)
        
        # --- Map results back to the original dataframe if MTF ---
        if self.timeframe:
            final_results = ma_results.reindex(base_df.index, method='ffill')
            self.df[self.ma_col] = final_results[self.ma_col]
        else:
            self.df[self.ma_col] = ma_results[self.ma_col]

        return self

    def analyze(self) -> Dict[str, Any]:
        """Provides a deep, bias-free analysis of the trend's momentum and acceleration."""
        # ✨ Bias-Free: Drop all NaNs first and get the last valid rows
        valid_df = self.df.dropna(subset=[self.ma_col, 'close'])
        if len(valid_df) < 3: # Need at least 3 points to calculate acceleration
            return {"status": "Insufficient Data", "analysis": {}}

        last = valid_df.iloc[-1]
        prev = valid_df.iloc[-2]
        prev_prev = valid_df.iloc[-3]

        close_price = last['close']
        ma_val = last[self.ma_col]
        
        # --- ✨ Deep Momentum Analysis ---
        # 1. Slope (Velocity)
        slope = ma_val - prev[self.ma_col]
        
        # 2. Acceleration (Change in Slope)
        prev_slope = prev[self.ma_col] - prev_prev[self.ma_col]
        acceleration = slope - prev_slope
        
        # --- Signal Logic ---
        signal = "Neutral"
        message = "No clear momentum signal."
        
        # A strong buy signal requires price to be above the MA, and the MA's slope to be positive and accelerating
        is_bullish = close_price > ma_val and slope > (ma_val * self.slope_threshold)
        is_bearish = close_price < ma_val and slope < -(ma_val * self.slope_threshold)

        if is_bullish:
            signal = "Buy"
            strength = "Strong" if acceleration > 0 else "Weakening"
            message = f"Bullish trend ({strength}). Price is above {self.ma_type} and slope is positive."
        elif is_bearish:
            signal = "Sell"
            strength = "Strong" if acceleration < 0 else "Weakening"
            message = f"Bearish trend ({strength}). Price is below {self.ma_type} and slope is negative."

        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "indicator_type": self.ma_type,
            "values": {
                "ma_value": round(ma_val, 5),
                "price": round(close_price, 5),
            },
            "analysis": {
                "signal": signal,
                "slope": round(slope, 5),
                "acceleration": round(acceleration, 5),
                "message": message
            }
        }
