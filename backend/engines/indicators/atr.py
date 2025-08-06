import pandas as pd
import numpy as np
from .base import BaseIndicator
import logging

logger = logging.getLogger(__name__)

class AtrIndicator(BaseIndicator):
    """
    ✨ UPGRADE v2.0 ✨
    محاسبه و تحلیل ATR با خروجی نرمال‌شده (درصد از قیمت) برای تحلیل بهتر نوسانات.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.period = self.params.get('period', 14)
        self.atr_col = f'atr_{self.period}'

    def calculate(self) -> pd.DataFrame:
        high_low = self.df['high'] - self.df['low']
        high_close = np.abs(self.df['high'] - self.df['close'].shift(1))
        low_close = np.abs(self.df['low'] - self.df['close'].shift(1))
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        # استفاده از ewm برای Wilder's Smoothing که معادل RMA است
        self.df[self.atr_col] = tr.ewm(alpha=1/self.period, adjust=False).mean()
        return self.df

    def analyze(self) -> dict:
        """
        ✨ ارتقا: علاوه بر مقدار خام ATR، درصد آن نسبت به قیمت را نیز برمی‌گرداند.
        """
        last_row = self.df.iloc[-1]
        atr_value = last_row[self.atr_col]
        close_price = last_row['close']
        
        if close_price == 0:
            atr_percent = 0
        else:
            atr_percent = (atr_value / close_price) * 100
        
        return {
            "value": round(atr_value, 5),
            "percent": round(atr_percent, 2)
        }
