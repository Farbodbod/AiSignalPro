import pandas as pd
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class MacdIndicator(BaseIndicator):
    """
    ✨ UPGRADE v2.0 ✨
    - Constructor standardized to use **kwargs.
    - Analyze method enhanced for clearer signal reporting.
    """

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        # استخراج پارامترها از kwargs با مقادیر پیش‌فرض
        self.fast_period = self.params.get('fast_period', 12)
        self.slow_period = self.params.get('slow_period', 26)
        self.signal_period = self.params.get('signal_period', 9)
        
        # تعریف نام ستون‌ها
        self.macd_col = 'macd_line'
        self.signal_col = 'macd_signal'
        self.hist_col = 'macd_hist'

    def calculate(self) -> pd.DataFrame:
        ema_fast = self.df['close'].ewm(span=self.fast_period, adjust=False).mean()
        ema_slow = self.df['close'].ewm(span=self.slow_period, adjust=False).mean()
        self.df[self.macd_col] = ema_fast - ema_slow
        self.df[self.signal_col] = self.df[self.macd_col].ewm(span=self.signal_period, adjust=False).mean()
        self.df[self.hist_col] = self.df[self.macd_col] - self.df[self.signal_col]
        return self.df

    def analyze(self) -> dict:
        last_row = self.df.iloc[-1]
        prev_row = self.df.iloc[-2]

        signal = "Neutral"
        
        # تشخیص کراس‌اوور خط MACD و خط سیگنال
        if prev_row[self.macd_col] < prev_row[self.signal_col] and last_row[self.macd_col] > last_row[self.signal_col]:
            signal = "Bullish Crossover"
        elif prev_row[self.macd_col] > prev_row[self.signal_col] and last_row[self.macd_col] < last_row[self.signal_col]:
            signal = "Bearish Crossover"
        # تشخیص کراس‌اوور خط صفر
        elif prev_row[self.macd_col] < 0 and last_row[self.macd_col] > 0:
            signal = "Bullish Centerline Cross"
        elif prev_row[self.macd_col] > 0 and last_row[self.macd_col] < 0:
            signal = "Bearish Centerline Cross"

        return {
            "macd_line": round(last_row[self.macd_col], 5),
            "signal_line": round(last_row[self.signal_col], 5),
            "histogram": round(last_row[self.hist_col], 5),
            "signal": signal
        }
