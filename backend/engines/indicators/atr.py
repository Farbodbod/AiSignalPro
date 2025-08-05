# engines/indicators/atr.py

import pandas as pd
import numpy as np
from .base import BaseIndicator

class AtrIndicator(BaseIndicator):
    """
    محاسبه اندیکاتور Average True Range (ATR)
    که یک معیار کلیدی برای اندازه‌گیری نوسانات بازار است.
    """
    def __init__(self, df: pd.DataFrame, period: int = 14):
        super().__init__(df, period=period)
        self.period = period
        self.atr_col = f'atr_{period}'

    def calculate(self) -> pd.DataFrame:
        high_low = self.df['high'] - self.df['low']
        high_close = np.abs(self.df['high'] - self.df['close'].shift(1))
        low_close = np.abs(self.df['low'] - self.df['close'].shift(1))
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        self.df[self.atr_col] = tr.ewm(alpha=1/self.period, adjust=False).mean()
        return self.df

    def analyze(self) -> dict:
        return {"value": self.df[self.atr_col].iloc[-1]}
