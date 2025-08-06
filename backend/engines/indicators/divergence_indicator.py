import pandas as pd
import numpy as np
import logging
from .base import BaseIndicator
from .zigzag import ZigzagIndicator
from .rsi import RsiIndicator

logger = logging.getLogger(__name__)

class DivergenceIndicator(BaseIndicator):
    """
    ✨ UPGRADE v2.0 ✨
    - Re-engineered to use the robust ZigzagIndicator for pivot detection.
    - Constructor standardized to use **kwargs.
    - More reliable and consistent divergence signals.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.zigzag_deviation = self.params.get('zigzag_deviation', 5.0)
        self.rsi_period = self.params.get('rsi_period', 14)

    def calculate(self) -> pd.DataFrame:
        # اطمینان از وجود RSI و ZigZag
        if f'rsi_{self.rsi_period}' not in self.df.columns:
            rsi_indicator = RsiIndicator(self.df, period=self.rsi_period)
            self.df = rsi_indicator.calculate()
        
        if f'zigzag_pivots_{self.zigzag_deviation}' not in self.df.columns:
            zigzag_indicator = ZigzagIndicator(self.df, deviation=self.zigzag_deviation)
            self.df = zigzag_indicator.calculate()
            
        return self.df

    def analyze(self) -> dict:
        zigzag_pivots_col = f'zigzag_pivots_{self.zigzag_deviation}'
        zigzag_prices_col = f'zigzag_prices_{self.zigzag_deviation}'
        rsi_col = f'rsi_{self.rsi_period}'

        pivots_df = self.df[self.df[zigzag_pivots_col] != 0].copy()
        if len(pivots_df) < 2:
            return {"type": "None", "strength": "Normal"}

        last_pivot = pivots_df.iloc[-1]
        prev_pivot = pivots_df.iloc[-2]

        result = {"type": "None", "strength": "Normal"}

        # بررسی واگرایی نزولی (Bearish Divergence): Higher High in Price, Lower High in RSI
        if last_pivot[zigzag_pivots_col] == 1 and prev_pivot[zigzag_pivots_col] == 1: # Two consecutive peaks
            if last_pivot[zigzag_prices_col] > prev_pivot[zigzag_prices_col] and \
               self.df.loc[last_pivot.name, rsi_col] < self.df.loc[prev_pivot.name, rsi_col]:
                result["type"] = "Bearish"
                if self.df.loc[last_pivot.name, rsi_col] > 65:
                    result["strength"] = "Strong"

        # بررسی واگرایی صعودی (Bullish Divergence): Lower Low in Price, Higher Low in RSI
        elif last_pivot[zigzag_pivots_col] == -1 and prev_pivot[zigzag_pivots_col] == -1: # Two consecutive troughs
            if last_pivot[zigzag_prices_col] < prev_pivot[zigzag_prices_col] and \
               self.df.loc[last_pivot.name, rsi_col] > self.df.loc[prev_pivot.name, rsi_col]:
                result["type"] = "Bullish"
                if self.df.loc[last_pivot.name, rsi_col] < 35:
                    result["strength"] = "Strong"
        
        return result
