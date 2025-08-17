# backend/engines/indicators/williams_r.py
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, List

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class WilliamsRIndicator(BaseIndicator):
    """
    Williams %R - (v5.0 - Dependency Injection Native)
    -------------------------------------------------------------------------
    This world-class version is re-engineered to natively support the Dependency
    Injection (DI) architecture. The core W%R calculation and analysis remain
    untouched, while the optional divergence detection feature now robustly consumes
    the ZigZag instance, making the entire indicator flawless and decoupled.
    """
    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], dependencies: Dict[str, BaseIndicator], **kwargs):
        super().__init__(df, params=params, dependencies=dependencies, **kwargs)
        self.period = int(self.params.get('period', 14))
        self.overbought = float(self.params.get('overbought', -20.0))
        self.oversold = float(self.params.get('oversold', -80.0))
        self.timeframe = self.params.get('timeframe')
        self.detect_divergence = bool(self.params.get('detect_divergence', True))
        self.divergence_lookback = int(self.params.get('divergence_lookback', 5))
        
        self.wr_col = 'WR' # Simplified, robust column name

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
        Calculates only the W%R value. ZigZag data is handled in the analyze phase.
        """
        if len(self.df) < self.period:
            logger.warning(f"Not enough data for Williams %R on {self.timeframe or 'base'}.")
            self.df[self.wr_col] = np.nan
            return self

        wr_results = self._calculate_wr(self.df)
        self.df[self.wr_col] = wr_results[self.wr_col]
        return self
    
    def _find_divergences(self, wr_df: pd.DataFrame) -> List[Dict[str, Any]]:
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
        
        analysis_df = wr_df.join(zigzag_df[[pivot_col, price_col]], how='left')
        analysis_df[self.wr_col] = analysis_df[self.wr_col].ffill()
        
        pivots_df = analysis_df[analysis_df[pivot_col] != 0].dropna(subset=[self.wr_col])
        if len(pivots_df) < 2: 
            return []
        
        last_pivot = pivots_df.iloc[-1]
        previous_pivots = pivots_df.iloc[-self.divergence_lookback:-1]
        divergences = []
        for i in range(len(previous_pivots)):
            prev_pivot = previous_pivots.iloc[i]
            price1, wr1 = prev_pivot[price_col], prev_pivot[self.wr_col]
            price2, wr2 = last_pivot[price_col], last_pivot[self.wr_col]
            if prev_pivot[pivot_col] == 1 and last_pivot[pivot_col] == 1: # Two peaks
                if price2 > price1 and wr2 < wr1: divergences.append({'type': 'Regular Bearish'})
                if price2 < price1 and wr2 > wr1: divergences.append({'type': 'Hidden Bearish'})
            elif prev_pivot[pivot_col] == -1 and last_pivot[pivot_col] == -1: # Two troughs
                if price2 < price1 and wr2 > wr1: divergences.append({'type': 'Regular Bullish'})
                if price2 > price1 and wr2 < wr1: divergences.append({'type': 'Hidden Bullish'})
        return divergences

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
        
        divergences = self._find_divergences(valid_df)
        
        return {
            "status": "OK", "timeframe": self.timeframe or 'Base',
            "values": {"wr": round(last_wr, 2)},
            "analysis": {
                "position": position,
                "crossover_signal": signal,
                "momentum": {"direction": momentum, "slope": round(slope, 2)},
                "divergences": divergences
            }
        }
