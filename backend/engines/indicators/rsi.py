import pandas as pd
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class RsiIndicator(BaseIndicator):
    """
    ✨ UPGRADE v2.0 ✨
    - Constructor standardized.
    - Analyze method enhanced to detect crossovers for stronger signals.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.period = self.params.get('period', 14)
        self.overbought = self.params.get('overbought', 70)
        self.oversold = self.params.get('oversold', 30)
        self.column_name = f'rsi_{self.period}'

    def calculate(self) -> pd.DataFrame:
        delta = self.df['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.ewm(alpha=1/self.period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/self.period, adjust=False).mean()
        rs = avg_gain / (avg_loss + 1e-12)
        self.df[self.column_name] = 100.0 - (100.0 / (1.0 + rs))
        return self.df

    def analyze(self) -> dict:
        last_rsi = self.df[self.column_name].iloc[-1]
        prev_rsi = self.df[self.column_name].iloc[-2]
        
        position = "Neutral"
        if last_rsi > self.overbought: position = "Overbought"
        elif last_rsi < self.oversold: position = "Oversold"
            
        signal = "Hold"
        if prev_rsi <= self.oversold and last_rsi > self.oversold:
            signal = "Exit Oversold (Buy)"
        elif prev_rsi >= self.overbought and last_rsi < self.overbought:
            signal = "Exit Overbought (Sell)"

        return {"value": round(last_rsi, 2), "position": position, "signal": signal}
