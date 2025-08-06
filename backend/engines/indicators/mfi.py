import pandas as pd
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class MfiIndicator(BaseIndicator):
    """
    ✨ UPGRADE v2.0 ✨
    - Constructor standardized.
    - Analyze method enhanced to detect crossovers.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.period = self.params.get('period', 14)
        self.overbought = self.params.get('overbought', 80)
        self.oversold = self.params.get('oversold', 20)
        self.mfi_col = f'mfi_{self.period}'

    def calculate(self) -> pd.DataFrame:
        tp = (self.df['high'] + self.df['low'] + self.df['close']) / 3
        raw_money_flow = tp * self.df['volume']
        price_diff = tp.diff(1)
        positive_money_flow = raw_money_flow.where(price_diff > 0, 0)
        negative_money_flow = raw_money_flow.where(price_diff < 0, 0)
        positive_mf_sum = positive_money_flow.rolling(window=self.period).sum()
        negative_mf_sum = negative_money_flow.rolling(window=self.period).sum()
        money_ratio = positive_mf_sum / (negative_mf_sum + 1e-12)
        self.df[self.mfi_col] = 100 - (100 / (1 + money_ratio))
        return self.df

    def analyze(self) -> dict:
        last_mfi = self.df[self.mfi_col].iloc[-1]
        prev_mfi = self.df[self.mfi_col].iloc[-2]
        
        position = "Neutral"
        if last_mfi > self.overbought: position = "Overbought"
        elif last_mfi < self.oversold: position = "Oversold"
            
        signal = "Hold"
        if prev_mfi <= self.oversold and last_mfi > self.oversold:
            signal = "Exit Oversold (Buy)"
        elif prev_mfi >= self.overbought and last_mfi < self.overbought:
            signal = "Exit Overbought (Sell)"

        return {"value": round(last_mfi, 2), "position": position, "signal": signal}
