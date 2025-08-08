import pandas as pd
import numpy as np
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class WilliamsRIndicator(BaseIndicator):
    """
    ✨ UPGRADE v2.1 - Smart Analysis ✨
    - Constructor standardized.
    - Analyze method enhanced to detect extreme conditions.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.period = self.params.get('period', 14)
        self.overbought_level = self.params.get('overbought', -20)
        self.oversold_level = self.params.get('oversold', -80)
        self.col_name = f'williams_r_{self.period}'

    def calculate(self) -> pd.DataFrame:
        highest_high = self.df['high'].rolling(window=self.period).max()
        lowest_low = self.df['low'].rolling(window=self.period).min()
        numerator = highest_high - self.df['close']
        denominator = highest_high - lowest_low
        self.df[self.col_name] = np.where(denominator == 0, -50, (numerator / denominator) * -100)
        return self.df

    def analyze(self) -> dict:
        last_value = self.df[self.col_name].iloc[-1]
        prev_value = self.df[self.col_name].iloc[-2] if len(self.df) > 1 else last_value
        
        analysis = {
            'indicator': self.__class__.__name__,
            'params': {'period': self.period, 'ob': self.overbought_level, 'os': self.oversold_level},
            'values': {'williams_r': round(last_value, 2)}
        }

        # ✨ منطق تحلیل جدید و هوشمندتر
        position = "Neutral Zone"
        if last_value >= self.overbought_level: position = "Overbought"
        elif last_value <= self.oversold_level: position = "Oversold"
        if last_value < -100: position = "Extreme Selling Pressure" # <-- حالت جدید
        if last_value > 0: position = "Extreme Buying Pressure" # <-- حالت جدید

        signal = "Hold"
        if prev_value <= self.oversold_level and last_value > self.oversold_level:
            signal = "Exit Oversold (Buy)"
        elif prev_value >= self.overbought_level and last_value < self.overbought_level:
            signal = "Exit Overbought (Sell)"
            
        analysis['position'] = position
        analysis['signal'] = signal
        analysis['message'] = f"Williams %R is in '{position}' state."
            
        return analysis
