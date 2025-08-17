# backend/engines/indicators/mfi.py
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, List

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class MfiIndicator(BaseIndicator):
    """
    Money Flow Index (MFI) - (v4.0 - Dependency Injection Native)
    -------------------------------------------------------------------------------------
    This world-class version is re-engineered to natively support the Dependency
    Injection (DI) architecture. The core MFI calculation and analysis remain
    untouched, while the optional divergence detection feature now robustly consumes
    the ZigZag instance, making the entire indicator flawless and decoupled.
    """
    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], dependencies: Dict[str, BaseIndicator], **kwargs):
        super().__init__(df, params=params, dependencies=dependencies, **kwargs)
        self.period = int(self.params.get('period', 14))
        self.overbought = float(self.params.get('overbought', 80.0))
        self.oversold = float(self.params.get('oversold', 20.0))
        self.extreme_overbought = float(self.params.get('extreme_overbought', 90.0))
        self.extreme_oversold = float(self.params.get('extreme_oversold', 10.0))
        self.timeframe = self.params.get('timeframe')
        self.detect_divergence = bool(self.params.get('detect_divergence', True))
        self.divergence_lookback = int(self.params.get('divergence_lookback', 5))
        
        self.mfi_col = 'MFI' # Simplified, robust column name

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
        mfi.fillna(50, inplace=True) # MFI starts from 50
        res[self.mfi_col] = mfi
        return res

    def calculate(self) -> 'MfiIndicator':
        """
        Calculates only the MFI value. ZigZag data is handled in the analyze phase.
        """
        if len(self.df) < self.period:
            logger.warning(f"Not enough data for MFI on {self.timeframe or 'base'}.")
            self.df[self.mfi_col] = np.nan
            return self

        mfi_results = self._calculate_mfi(self.df)
        self.df[self.mfi_col] = mfi_results[self.mfi_col]
        return self
    
    def _find_divergences(self, mfi_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Finds divergences by consuming the injected ZigZag instance.
        """
        if not self.detect_divergence: 
            return []

        zigzag_instance = self.dependencies.get('zigzag')
        if not zigzag_instance:
            logger.debug(f"[{self.__class__.__name__}] ZigZag dependency not provided for divergence detection on {self.timeframe}.")
            return []

        zigzag_df = zigzag_instance.df
        pivots_col_options = [col for col in zigzag_df.columns if 'PIVOTS' in col.upper()]
        prices_col_options = [col for col in zigzag_df.columns if 'PRICES' in col.upper()]

        if not pivots_col_options or not prices_col_options:
            logger.warning(f"[{self.__class__.__name__}] Could not find pivot/price columns in ZigZag data for divergence detection.")
            return []
        
        pivot_col = pivots_col_options[0]
        price_col = prices_col_options[0]
        
        # Join ZigZag data with MFI data for analysis
        analysis_df = mfi_df.join(zigzag_df[[pivot_col, price_col]], how='left')
        analysis_df[self.mfi_col] = analysis_df[self.mfi_col].ffill() # Forward-fill MFI values onto pivot points
        
        pivots_df = analysis_df[analysis_df[pivot_col] != 0].dropna(subset=[self.mfi_col])
        if len(pivots_df) < 2: 
            return []
        
        last_pivot = pivots_df.iloc[-1]
        previous_pivots = pivots_df.iloc[-self.divergence_lookback:-1]
        divergences = []
        for i in range(len(previous_pivots)):
            prev_pivot = previous_pivots.iloc[i]
            price1, mfi1 = prev_pivot[price_col], prev_pivot[self.mfi_col]
            price2, mfi2 = last_pivot[price_col], last_pivot[self.mfi_col]
            if prev_pivot[pivot_col] == 1 and last_pivot[pivot_col] == 1: # Two peaks
                if price2 > price1 and mfi2 < mfi1: divergences.append({'type': 'Regular Bearish'})
                if price2 < price1 and mfi2 > mfi1: divergences.append({'type': 'Hidden Bearish'})
            elif prev_pivot[pivot_col] == -1 and last_pivot[pivot_col] == -1: # Two troughs
                if price2 < price1 and mfi2 > mfi1: divergences.append({'type': 'Regular Bullish'})
                if price2 > price1 and mfi2 < mfi1: divergences.append({'type': 'Hidden Bullish'})
        return divergences

    def analyze(self) -> Dict[str, Any]:
        """
        Provides a multi-faceted analysis of money flow. The core MFI analysis
        and the divergence-finding algorithm are 100% preserved.
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
            
        divergences = self._find_divergences(valid_df)
        
        return {
            "status": "OK", "timeframe": self.timeframe or 'Base',
            "values": {"mfi": round(last_mfi, 2)},
            "analysis": {
                "position": position,
                "crossover_signal": signal,
                "divergences": divergences
            }
        }
