import pandas as pd
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class WhaleIndicator(BaseIndicator):
    """
    ✨ UPGRADE v2.0 ✨
    - Constructor standardized to use **kwargs.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.period = self.params.get('period', 20)
        self.spike_multiplier = self.params.get('spike_multiplier', 3.5)
        self.vol_ma_col = f'volume_ma_{self.period}'

    def calculate(self) -> pd.DataFrame:
        self.df[self.vol_ma_col] = self.df['volume'].rolling(window=self.period, min_periods=self.period).mean()
        return self.df

    def analyze(self) -> dict:
        if self.vol_ma_col not in self.df.columns or self.df[self.vol_ma_col].isnull().all():
            return {"status": "Not Enough Data", "spike_factor": 0, "pressure": "Unknown"}
        last_candle = self.df.iloc[-1]
        last_volume = last_candle['volume']; avg_volume = last_candle[self.vol_ma_col]
        status, pressure, spike_factor = "Normal Activity", "Neutral", 0
        if avg_volume > 0: spike_factor = round(last_volume / avg_volume, 2)
        if spike_factor > self.spike_multiplier:
            status = "Whale Activity Detected"
            if last_candle['close'] > last_candle['open']: pressure = "Buying Pressure"
            elif last_candle['close'] < last_candle['open']: pressure = "Selling Pressure"
            else: pressure = "Indecisive"
        return {"status": status, "spike_factor": spike_factor, "pressure": pressure}
