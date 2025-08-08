import pandas as pd
import numpy as np
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class EMACrossIndicator(BaseIndicator):
    """
    ✨ FINAL VERSION - JSON Safe ✨
    این نسخه نهایی و استاندارد اندیکاتور EMA Cross است.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.short_period = self.params.get('short_period', 9)
        self.long_period = self.params.get('long_period', 21)
        if self.short_period >= self.long_period:
            raise ValueError(f"Short period ({self.short_period}) must be less than long period ({self.long_period}).")
        self.signal_col_name = f'signal_ema_cross_{self.short_period}_{self.long_period}'
        self.short_ema_col = f'ema_{self.short_period}'
        self.long_ema_col = f'ema_{self.long_period}'

    def calculate(self) -> pd.DataFrame:
        close_col = self.params.get('close_col', 'close')
        self.df[self.short_ema_col] = self.df[close_col].ewm(span=self.short_period, adjust=False).mean()
        self.df[self.long_ema_col] = self.df[close_col].ewm(span=self.long_period, adjust=False).mean()
        prev_short_ema = self.df[self.short_ema_col].shift(1)
        prev_long_ema = self.df[self.long_ema_col].shift(1)
        condition_bullish = (prev_short_ema < prev_long_ema) & (self.df[self.short_ema_col] > self.df[self.long_ema_col])
        condition_bearish = (prev_short_ema > prev_long_ema) & (self.df[self.short_ema_col] < self.df[self.long_ema_col])
        self.df[self.signal_col_name] = np.where(condition_bullish, 1, np.where(condition_bearish, -1, 0))
        return self.df

    def analyze(self) -> dict:
        last_row = self.df.iloc[-1]
        signal_value = int(last_row[self.signal_col_name])
        
        # ✨ اصلاحیه کلیدی: استفاده از __class__.__name__ برای دریافت نام به صورت متن
        analysis = {'indicator': self.__class__.__name__, 'params': {'short': self.short_period, 'long': self.long_period}}
        
        if signal_value == 1:
            analysis['signal'] = 'buy'
            analysis['message'] = f"Golden Cross ({self.short_period}/{self.long_period})"
        elif signal_value == -1:
            analysis['signal'] = 'sell'
            analysis['message'] = f"Death Cross ({self.short_period}/{self.long_period})"
        else:
            analysis['signal'] = 'neutral'
            analysis['message'] = "No Crossover"
            
        analysis['values'] = {
            self.short_ema_col: round(last_row[self.short_ema_col], 5),
            self.long_ema_col: round(last_row[self.long_ema_col], 5)
        }
        return analysis
