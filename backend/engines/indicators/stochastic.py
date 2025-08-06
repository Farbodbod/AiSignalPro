import pandas as pd
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class StochasticIndicator(BaseIndicator):
    """
    ✨ UPGRADE v2.0 ✨
    - Constructor standardized.
    - Analyze method refined for clarity.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.k_period = self.params.get('k_period', 14)
        self.d_period = self.params.get('d_period', 3)
        self.smooth_k = self.params.get('smooth_k', 3)
        self.k_col = f'stoch_k_{self.k_period}_{self.d_period}'
        self.d_col = f'stoch_d_{self.k_period}_{self.d_period}'

    def calculate(self) -> pd.DataFrame:
        low_min = self.df['low'].rolling(window=self.k_period).min()
        high_max = self.df['high'].rolling(window=self.k_period).max()
        fast_k = 100 * ((self.df['close'] - low_min) / (high_max - low_min + 1e-12))
        self.df[self.k_col] = fast_k.rolling(window=self.smooth_k).mean()
        self.df[self.d_col] = self.df[self.k_col].rolling(window=self.d_period).mean()
        return self.df

    def analyze(self) -> dict:
        last_row = self.df.iloc[-1]; prev_row = self.df.iloc[-2]
        k_val = last_row[self.k_col]; d_val = last_row[self.d_col]

        position = "Neutral"
        if k_val > 80 and d_val > 80: position = "Overbought"
        elif k_val < 20 and d_val < 20: position = "Oversold"
        
        signal = "Hold"
        if prev_row[self.k_col] < prev_row[self.d_col] and k_val > d_val:
            signal = "Bullish Crossover"
            if k_val < 30: signal = "Strong Bullish Crossover"
        elif prev_row[self.k_col] > prev_row[self.d_col] and k_val < d_val:
            signal = "Bearish Crossover"
            if k_val > 70: signal = "Strong Bearish Crossover"

        return {
            "percent_k": round(k_val, 2), "percent_d": round(d_val, 2),
            "position": position, "signal": signal
        }
