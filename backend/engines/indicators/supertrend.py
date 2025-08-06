import pandas as pd
import numpy as np
import logging
from .base import BaseIndicator
from .atr import AtrIndicator # ✨ 1. استفاده از AtrIndicator استاندارد

logger = logging.getLogger(__name__)

class SuperTrendIndicator(BaseIndicator):
    """
    ✨ UPGRADE v2.0 ✨
    - Constructor standardized.
    - Uses the standard AtrIndicator for ATR calculation (DRY principle).
    - Cleaner and more robust implementation.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.period = self.params.get('period', 10)
        self.multiplier = self.params.get('multiplier', 3.0)
        self.supertrend_col = f'supertrend_{self.period}_{self.multiplier}'
        self.direction_col = f'supertrend_dir_{self.period}_{self.multiplier}'

    def calculate(self) -> pd.DataFrame:
        df = self.df.copy()
        
        # ✨ 2. محاسبه ATR با استفاده از کلاس استاندارد
        atr_indicator = AtrIndicator(df, period=self.period)
        df = atr_indicator.calculate()
        atr_col = atr_indicator.atr_col
        atr = df[atr_col]
        
        basic_upperband = (df['high'] + df['low']) / 2 + self.multiplier * atr
        basic_lowerband = (df['high'] + df['low']) / 2 - self.multiplier * atr

        supertrend = pd.Series(np.nan, index=df.index)
        direction = pd.Series(np.nan, index=df.index)

        # منطق حلقه که برای سوپرترند ضروری است، حفظ می‌شود
        for i in range(1, len(df)):
            st_prev = supertrend.iloc[i-1]
            if pd.isna(st_prev): # مقدار اولیه
                st_prev = df['close'].iloc[i-1]

            if df['close'].iloc[i-1] > st_prev:
                supertrend.iloc[i] = max(basic_lowerband.iloc[i], st_prev)
            else:
                supertrend.iloc[i] = min(basic_upperband.iloc[i], st_prev)
            
            if df['close'].iloc[i] > supertrend.iloc[i]:
                direction.iloc[i] = 1
            else:
                direction.iloc[i] = -1
        
        self.df[self.supertrend_col] = supertrend
        self.df[self.direction_col] = direction
        return self.df

    def analyze(self) -> dict:
        # ... این متد از قبل بهینه و صحیح بود و بدون تغییر باقی می‌ماند ...
        last_row = self.df.iloc[-1]; prev_row = self.df.iloc[-2]
        last_dir = last_row[self.direction_col]; prev_dir = prev_row[self.direction_col]
        trend = "Uptrend" if last_dir == 1 else "Downtrend"
        signal = "Trend Continuation"
        if last_dir == 1 and prev_dir == -1: signal = "Bullish Trend Change"
        elif last_dir == -1 and prev_dir == 1: signal = "Bearish Trend Change"
        return {"value": round(last_row[self.supertrend_col], 5), "trend": trend, "signal": signal}
