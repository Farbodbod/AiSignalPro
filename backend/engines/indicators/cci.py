import pandas as pd
import numpy as np
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class CciIndicator(BaseIndicator):
    """ ✨ UPGRADE v2.0 ✨ """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.period = self.params.get('period', 20)
        self.constant = self.params.get('constant', 0.015)
        self.cci_col = f'cci_{self.period}'

    def calculate(self) -> pd.DataFrame:
        # ... منطق محاسبه بدون تغییر باقی می‌ماند ...
        tp = (self.df['high'] + self.df['low'] + self.df['close']) / 3
        ma_tp = tp.rolling(window=self.period).mean()
        mean_dev = tp.rolling(window=self.period).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
        self.df[self.cci_col] = (tp - ma_tp) / (self.constant * mean_dev + 1e-12)
        return self.df

    def analyze(self) -> dict:
        # ... ✨ ارتقا: تحلیل خواناتر و دقیق‌تر ...
        last_val = self.df[self.cci_col].iloc[-1]; prev_val = self.df[self.cci_col].iloc[-2]
        
        position = "Neutral"
        if last_val > 100: position = "Overbought"
        elif last_val < -100: position = "Oversold"
        
        signal = "Hold"
        if prev_val <= 100 and last_val > 100: signal = "Bullish Cross"
        elif prev_val >= -100 and last_val < -100: signal = "Bearish Cross"
        elif prev_val > 100 and last_val < 100: signal = "Exit Buy Signal"
        elif prev_val < -100 and last_val > -100: signal = "Exit Sell Signal"

        return {"value": round(last_val, 2), "position": position, "signal": signal}
