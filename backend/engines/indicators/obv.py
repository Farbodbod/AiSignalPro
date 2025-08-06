import pandas as pd
import numpy as np
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class ObvIndicator(BaseIndicator):
    """
    ✨ UPGRADE v2.0 ✨
    - Constructor standardized to use **kwargs.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.ma_period = self.params.get('ma_period', 20)
        self.obv_col = 'obv'
        self.obv_ma_col = f'obv_ma_{self.ma_period}'

    def calculate(self) -> pd.DataFrame:
        obv = np.where(self.df['close'] > self.df['close'].shift(1), self.df['volume'], 
              np.where(self.df['close'] < self.df['close'].shift(1), -self.df['volume'], 0)).cumsum()
        self.df[self.obv_col] = obv
        self.df[self.obv_ma_col] = self.df[self.obv_col].rolling(window=self.ma_period).mean()
        return self.df

    def analyze(self) -> dict:
        last_row = self.df.iloc[-1]; prev_row = self.df.iloc[-2]
        obv_value = last_row[self.obv_col]; obv_ma_value = last_row[self.obv_ma_col]
        trend = "Bullish Momentum" if obv_value > obv_ma_value else "Bearish Momentum"
        signal = "Volume Trend Continuation"
        if prev_row[self.obv_col] < prev_row[self.obv_ma_col] and obv_value > obv_ma_value:
            signal = "Bullish Volume Crossover"
        elif prev_row[self.obv_col] > prev_row[self.obv_ma_col] and obv_value < obv_ma_value:
            signal = "Bearish Volume Crossover"
        return {
            "obv_value": int(obv_value), "obv_ma_value": int(obv_ma_value),
            "trend": trend, "signal": signal
        }
