import pandas as pd
import numpy as np
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class AdxIndicator(BaseIndicator):
    """ ✨ UPGRADE v2.0 - Advanced ADX Indicator with bug fix for Timestamp mismatch """
    
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.period = self.params.get('period', 14)
        self.adx_col = f'adx_{self.period}'
        self.plus_di_col = f'plus_di_{self.period}'
        self.minus_di_col = f'minus_di_{self.period}'

    def calculate(self) -> pd.DataFrame:
        df = self.df.copy()

        # --- True Range (TR) ---
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift(1))
        low_close = np.abs(df['low'] - df['close'].shift(1))
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1 / self.period, adjust=False).mean()

        # --- Directional Movement (DM) ---
        move_up = df['high'].diff()
        move_down = df['low'].diff()
        plus_dm = np.where((move_up > move_down) & (move_up > 0), move_up, 0.0)
        minus_dm = np.where((move_down > move_up) & (move_down > 0), move_down, 0.0)

        # --- Smooth with matching index to avoid Timestamp warning ---
        plus_dm_smooth = pd.Series(plus_dm, index=df.index).ewm(alpha=1 / self.period, adjust=False).mean()
        minus_dm_smooth = pd.Series(minus_dm, index=df.index).ewm(alpha=1 / self.period, adjust=False).mean()

        self.df[self.plus_di_col] = (plus_dm_smooth / (atr + 1e-12)) * 100
        self.df[self.minus_di_col] = (minus_dm_smooth / (atr + 1e-12)) * 100

        dx = (np.abs(self.df[self.plus_di_col] - self.df[self.minus_di_col]) /
              (self.df[self.plus_di_col] + self.df[self.minus_di_col] + 1e-12)) * 100

        self.df[self.adx_col] = dx.ewm(alpha=1 / self.period, adjust=False).mean()

        return self.df

    def analyze(self) -> dict:
        last_row = self.df.iloc[-1]
        prev_row = self.df.iloc[-2]

        adx_val = last_row[self.adx_col]
        prev_adx_val = prev_row[self.adx_col]
        plus_di = last_row[self.plus_di_col]
        minus_di = last_row[self.minus_di_col]

        trend_strength = "No Trend"
        if 20 < adx_val <= 25:
            trend_strength = "Weak Trend"
        elif 25 < adx_val <= 40:
            trend_strength = "Strong Trend"
        elif adx_val > 40:
            trend_strength = "Very Strong Trend"

        trend_direction = "Neutral"
        if plus_di > minus_di:
            trend_direction = "Bullish"
        elif minus_di > plus_di:
            trend_direction = "Bearish"

        is_strengthening = adx_val > prev_adx_val

        return {
            "adx": round(adx_val, 2),
            "plus_di": round(plus_di, 2),
            "minus_di": round(minus_di, 2),
            "strength": trend_strength,
            "direction": trend_direction,
            "is_strengthening": is_strengthening,
            "signal": f"{trend_strength} ({trend_direction}) - {'Strengthening' if is_strengthening else 'Weakening'}"
        }
