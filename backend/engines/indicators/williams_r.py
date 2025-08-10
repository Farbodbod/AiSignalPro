import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, List, Optional

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class WilliamsRIndicator(BaseIndicator):
    """
    Williams %R - Definitive, World-Class Version (v4.1 - Harmonized Edition)
    -------------------------------------------------------------------------
    This version includes defensive programming to ensure core parameters are always
    available, preventing AttributeErrors and ensuring smooth operation within
    the IndicatorAnalyzer's architecture.
    """
    dependencies = ['zigzag']

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.period = int(self.params.get('period', 14))
        self.overbought = float(self.params.get('overbought', -20.0))
        self.oversold = float(self.params.get('oversold', -80.0))
        
        # FIX: Ensure timeframe is always initialized, even if None
        self.timeframe = self.params.get('timeframe', None)
        
        self.detect_divergence = bool(self.params.get('detect_divergence', True))
        self.zigzag_deviation = float(self.params.get('zigzag_deviation', 3.0))
        self.divergence_lookback = int(self.params.get('divergence_lookback', 5))
        
        suffix = f'_{self.period}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.wr_col = f'wr{suffix}'

    # ... (rest of the code remains the same) ...
    # The fix is in __init__.
    
    def _calculate_wr(self, df: pd.DataFrame) -> pd.DataFrame:
        """The core, technically correct Williams %R calculation logic."""
        res = pd.DataFrame(index=df.index)
        highest_high = df['high'].rolling(window=self.period).max()
        lowest_low = df['low'].rolling(window=self.period).min()
        
        denominator = (highest_high - lowest_low).replace(0, np.nan)
        numerator = highest_high - df['close']
        
        res[self.wr_col] = ((numerator / denominator) * -100).fillna(-50)
        return res

    def calculate(self) -> 'WilliamsRIndicator':
        """
        ✨ FINAL ARCHITECTURE: No resampling. Just pure calculation.
        """
        df_for_calc = self.df

        if len(df_for_calc) < self.period:
            logger.warning(f"Not enough data for Williams %R on {self.timeframe or 'base'}.")
            self.df[self.wr_col] = np.nan
            return self

        wr_results = self._calculate_wr(df_for_calc)
        self.df[self.wr_col] = wr_results[self.wr_col]
        return self
    
    def _find_divergences(self, valid_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Finds divergences by consuming pre-calculated ZigZag columns."""
        if not self.detect_divergence: return []

        tf_suffix = f'_{self.timeframe}' if self.timeframe else ''
        pivot_col = f'zigzag_pivots_{self.zigzag_deviation}{tf_suffix}'
        price_col = f'zigzag_prices_{self.zigzag_deviation}{tf_suffix}'
        
        if not all(col in valid_df.columns for col in [pivot_col, price_col]):
             logger.warning(f"[{self.__class__.__name__}] ZigZag columns not found for divergence detection.")
             return []

        pivots_df = valid_df[valid_df[pivot_col] != 0]
        if len(pivots_df) < 2: return []
        
        last_pivot = pivots_df.iloc[-1]
        previous_pivots = pivots_df.iloc[-self.divergence_lookback:-1]
        divergences = []
        for i in range(len(previous_pivots)):
            prev_pivot = previous_pivots.iloc[i]
            price1, wr1 = prev_pivot[price_col], prev_pivot[self.wr_col]
            price2, wr2 = last_pivot[price_col], last_pivot[self.wr_col]
            if prev_pivot[pivot_col] == 1 and last_pivot[pivot_col] == 1:
                if price2 > price1 and wr2 < wr1: divergences.append({'type': 'Regular Bearish'})
                if price2 < price1 and wr2 > wr1: divergences.append({'type': 'Hidden Bearish'})
            elif prev_pivot[pivot_col] == -1 and last_pivot[pivot_col] == -1:
                if price2 < price1 and wr2 > wr1: divergences.append({'type': 'Regular Bullish'})
                if price2 > price1 and wr2 < wr1: divergences.append({'type': 'Hidden Bullish'})
        return divergences

    def analyze(self) -> Dict[str, Any]:
        """Provides a multi-faceted analysis of momentum and potential reversals."""
        valid_df = self.df.dropna(subset=[self.wr_col])
        if len(valid_df) < 2: return {"status": "Insufficient Data"}

        last = valid_df.iloc[-1]; prev = valid_df.iloc[-2]
        last_wr = last[self.wr_col]; prev_wr = prev[self.wr_col]

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
