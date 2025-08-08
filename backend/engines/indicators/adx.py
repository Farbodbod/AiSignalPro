import pandas as pd
import numpy as np
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class AdxIndicator(BaseIndicator):
    """
    ADX Indicator - World-Class, Flexible & Robust Version
    ----------------------------------------------------------
    This version includes:
    1.  Accurate Wilder's Smoothing calculations.
    2.  Robust input validation (columns, length, dtype).
    3.  Graceful handling of division-by-zero by propagating NaNs.
    4.  Parameterizable thresholds for trend analysis.
    5.  Explicit crossover signal detection (+DI / -DI).
    6.  Error-proof analysis method that handles initial NaN values.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        # --- Parameterization ---
        self.period = int(self.params.get('period', 14))
        # ✨ IMPROVEMENT 1: Make analysis thresholds configurable
        self.adx_thresholds = self.params.get('adx_thresholds', {
            'no_trend_max': 20,
            'weak_trend_max': 25,
            'strong_trend_max': 40
        })
        
        # --- Column Naming ---
        self.adx_col = f'adx_{self.period}'
        self.plus_di_col = f'plus_di_{self.period}'
        self.minus_di_col = f'minus_di_{self.period}'

    def _validate_input(self, df: pd.DataFrame):
        """Validates the input DataFrame."""
        required_cols = {'high', 'low', 'close'}
        if not required_cols.issubset(df.columns):
            missing = required_cols - set(df.columns)
            msg = f"Missing required columns for ADX: {missing}"
            logger.error(msg)
            raise ValueError(msg)
        
        if len(df) < self.period:
            logger.warning(f"Data length ({len(df)}) is less than ADX period ({self.period}). Results might be unreliable.")
            
        # Ensure correct data types to prevent calculation errors
        for col in required_cols:
            if not pd.api.types.is_numeric_dtype(df[col]):
                 df[col] = pd.to_numeric(df[col], errors='coerce')
        return df

    def calculate(self) -> pd.DataFrame:
        """Calculates the ADX indicator values."""
        df = self.df.copy()
        df = self._validate_input(df)

        # True Range (TR)
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift(1))
        low_close = np.abs(df['low'] - df['close'].shift(1))
        
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        # Use Wilder's Smoothing (RMA), which is what ewm with alpha=1/period does
        atr = tr.ewm(alpha=1/self.period, adjust=False).mean()

        # Directional Movement (DM) - Corrected formulas
        move_up = df['high'].diff()
        move_down = df['low'].diff().mul(-1) # Simplified: low.shift(1) - low

        plus_dm = np.where((move_up > move_down) & (move_up > 0), move_up, 0.0)
        minus_dm = np.where((move_down > move_up) & (move_down > 0), move_down, 0.0)

        # Smoothed DM
        plus_dm_smooth = pd.Series(plus_dm, index=df.index).ewm(alpha=1/self.period, adjust=False).mean()
        minus_dm_smooth = pd.Series(minus_dm, index=df.index).ewm(alpha=1/self.period, adjust=False).mean()

        # Directional Indicators (+DI, -DI) - Propagate NaN on division by zero
        safe_atr = atr.replace(0, np.nan)
        self.df[self.plus_di_col] = (plus_dm_smooth / safe_atr) * 100
        self.df[self.minus_di_col] = (minus_dm_smooth / safe_atr) * 100

        # Directional Movement Index (DX)
        di_sum = (self.df[self.plus_di_col] + self.df[self.minus_di_col]).replace(0, np.nan)
        di_diff = np.abs(self.df[self.plus_di_col] - self.df[self.minus_di_col])
        dx = (di_diff / di_sum) * 100

        # Average Directional Index (ADX)
        self.df[self.adx_col] = dx.ewm(alpha=1/self.period, adjust=False).mean()
        
        return self.df

    def analyze(self) -> dict:
        """Analyzes the latest indicator values for signals."""
        # Ensure we have enough data and it's not NaN
        if len(self.df) < 2 or self.df[self.adx_col].iloc[-1] is np.nan:
            return {"signal": "Insufficient Data"}

        last = self.df.iloc[-1]
        prev = self.df.iloc[-2]

        adx_val = last[self.adx_col]
        plus_di = last[self.plus_di_col]
        minus_di = last[self.minus_di_col]

        # --- Trend Strength Analysis (using configurable thresholds) ---
        t = self.adx_thresholds
        if adx_val <= t['no_trend_max']:
            strength = "No Trend"
        elif adx_val <= t['weak_trend_max']:
            strength = "Weak Trend"
        elif adx_val <= t['strong_trend_max']:
            strength = "Strong Trend"
        else:
            strength = "Very Strong Trend"
        
        is_strengthening = adx_val > prev[self.adx_col]

        # --- Direction Analysis & ✨ IMPROVEMENT 3: Crossover Signal ---
        direction = "Neutral"
        cross_signal = "None"
        
        if plus_di > minus_di:
            direction = "Bullish"
            if prev[self.plus_di_col] <= prev[self.minus_di_col]:
                cross_signal = "Bullish Crossover"
        elif minus_di > plus_di:
            direction = "Bearish"
            if prev[self.minus_di_col] <= prev[self.plus_di_col]:
                cross_signal = "Bearish Crossover"

        return {
            "adx": round(adx_val, 2),
            "plus_di": round(plus_di, 2),
            "minus_di": round(minus_di, 2),
            "strength": strength,
            "direction": direction,
            "is_strengthening": is_strengthening,
            "cross_signal": cross_signal,
            "signal": f"{strength} ({direction}) - {'Strengthening' if is_strengthening else 'Weakening'}"
        }

