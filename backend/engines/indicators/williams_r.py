# backend/engines/indicators/williams_r.py
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class WilliamsRIndicator(BaseIndicator):
    """
    Williams %R - (v5.1 - Pure Calculation Engine)
    -------------------------------------------------------------------------
    This world-class version is a pure implementation of the Williams %R indicator.
    It has no external dependencies and serves as a foundational data provider.
    Divergence detection is correctly delegated to specialist indicators.
    """
    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], dependencies: Dict[str, BaseIndicator], **kwargs):
        super().__init__(df, params=params, dependencies=dependencies, **kwargs)
        self.period = int(self.params.get('period', 14))
        self.overbought = float(self.params.get('overbought', -20.0))
        self.oversold = float(self.params.get('oversold', -80.0))
        self.timeframe = self.params.get('timeframe')
        
        self.wr_col = 'WR'

    def _calculate_wr(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        The core, technically correct Williams %R calculation logic.
        This function's internal algorithm is 100% preserved.
        """
        res = pd.DataFrame(index=df.index)
        highest_high = df['high'].rolling(window=self.period).max()
        lowest_low = df['low'].rolling(window=self.period).min()
        
        denominator = (highest_high - lowest_low).replace(0, np.nan)
        numerator = highest_high - df['close']
        
        res[self.wr_col] = ((numerator / denominator) * -100).fillna(-50)
        return res

    def calculate(self) -> 'WilliamsRIndicator':
        """
        Calculates only the W%R value.
        """
        if len(self.df) < self.period:
            logger.warning(f"Not enough data for Williams %R on {self.timeframe or 'base'}.")
            self.df[self.wr_col] = np.nan
            return self

        wr_results = self._calculate_wr(self.df)
        self.df[self.wr_col] = wr_results[self.wr_col]
        return self

    def analyze(self) -> Dict[str, Any]:
        """
        Provides a multi-faceted analysis of momentum and potential reversals.
        The core analysis logic is 100% preserved.
        """
        valid_df = self.df.dropna(subset=[self.wr_col])
        if len(valid_df) < 2: 
            return {"status": "Insufficient Data"}

        last = valid_df.iloc[-1]
        prev = valid_df.iloc[-2]
        last_wr = last[self.wr_col]
        prev_wr = prev[self.wr_col]

        position = "Neutral"
        if last_wr >= self.overbought: position = "Overbought"
        elif last_wr <= self.oversold: position = "Oversold"
            
        signal = "Hold"
        if prev_wr <= self.oversold and last_wr > self.oversold: signal = "Oversold Exit (Buy)"
        elif prev_wr >= self.overbought and last_wr < self.overbought: signal = "Overbought Exit (Sell)"

        slope = last_wr - prev_wr
        momentum = "Rising" if slope > 0 else "Falling" if slope < 0 else "Flat"
        
        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "values": {"wr": round(last_wr, 2)},
            "analysis": {
                "position": position,
                "crossover_signal": signal,
                "momentum": {"direction": momentum, "slope": round(slope, 2)},
                "divergences": [] # Returns an empty list as per the pure architecture
            }
        }
