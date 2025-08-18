# backend/engines/indicators/mfi.py
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class MfiIndicator(BaseIndicator):
    """
    Money Flow Index (MFI) - (v4.1 - Pure Calculation Engine)
    -------------------------------------------------------------------------------------
    This world-class version is a pure implementation of the MFI indicator.
    It has no external dependencies and serves as a foundational data provider.
    Divergence detection is correctly delegated to specialist indicators, adhering
    to the Single Responsibility Principle for maximum stability and modularity.
    """
    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], dependencies: Dict[str, BaseIndicator], **kwargs):
        super().__init__(df, params=params, dependencies=dependencies, **kwargs)
        self.period = int(self.params.get('period', 14))
        self.overbought = float(self.params.get('overbought', 80.0))
        self.oversold = float(self.params.get('oversold', 20.0))
        self.extreme_overbought = float(self.params.get('extreme_overbought', 90.0))
        self.extreme_oversold = float(self.params.get('extreme_oversold', 10.0))
        self.timeframe = self.params.get('timeframe')
        
        self.mfi_col = 'MFI'

    def _calculate_mfi(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        The core, technically correct MFI calculation logic.
        This function's internal algorithm is 100% preserved.
        """
        res = pd.DataFrame(index=df.index)
        
        tp = (df['high'] + df['low'] + df['close']) / 3
        raw_money_flow = tp * df['volume']
        price_diff = tp.diff(1)
        
        pos_flow = np.where(price_diff > 0, raw_money_flow, 0)
        neg_flow = np.where(price_diff < 0, raw_money_flow, 0)

        pos_mf_sum = pd.Series(pos_flow, index=df.index).rolling(window=self.period).sum()
        neg_mf_sum = pd.Series(neg_flow, index=df.index).rolling(window=self.period).sum()

        money_ratio = pos_mf_sum / neg_mf_sum.replace(0, np.nan)
        mfi = 100 - (100 / (1 + money_ratio))
        mfi.fillna(50, inplace=True)
        res[self.mfi_col] = mfi
        return res

    def calculate(self) -> 'MfiIndicator':
        """
        Calculates only the MFI value.
        """
        if len(self.df) < self.period:
            logger.warning(f"Not enough data for MFI on {self.timeframe or 'base'}.")
            self.df[self.mfi_col] = np.nan
            return self

        mfi_results = self._calculate_mfi(self.df)
        self.df[self.mfi_col] = mfi_results[self.mfi_col]
        return self
    
    def analyze(self) -> Dict[str, Any]:
        """
        Provides a multi-faceted analysis of money flow. The core MFI analysis
        logic is 100% preserved.
        """
        valid_df = self.df.dropna(subset=[self.mfi_col])
        if len(valid_df) < 2: 
            return {"status": "Insufficient Data"}
        
        last = valid_df.iloc[-1]
        prev = valid_df.iloc[-2]
        last_mfi = last[self.mfi_col]
        prev_mfi = prev[self.mfi_col]

        position = "Neutral"
        if last_mfi >= self.extreme_overbought: position = "Extremely Overbought"
        elif last_mfi >= self.overbought: position = "Overbought"
        elif last_mfi <= self.extreme_oversold: position = "Extremely Oversold"
        elif last_mfi <= self.oversold: position = "Oversold"

        signal = "Hold"
        if prev_mfi <= self.oversold and last_mfi > self.oversold: signal = "Oversold Exit (Buy)"
        elif prev_mfi >= self.overbought and last_mfi < self.overbought: signal = "Overbought Exit (Sell)"
        elif prev_mfi <= 50 and last_mfi > 50: signal = "Bullish Centerline Cross"
        elif prev_mfi >= 50 and last_mfi < 50: signal = "Bearish Centerline Cross"
            
        return {
            "status": "OK", "timeframe": self.timeframe or 'Base',
            "values": {"mfi": round(last_mfi, 2)},
            "analysis": {
                "position": position,
                "crossover_signal": signal,
                "divergences": [] # Returns an empty list as per the pure architecture
            }
        }
