import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, List, Optional

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class StochasticIndicator(BaseIndicator):
    """
    Stochastic Oscillator - Definitive, World-Class Version (v4.0 - Final Architecture)
    -----------------------------------------------------------------------------------
    This advanced version provides a multi-faceted analysis of momentum by consuming
    pre-calculated ZigZag columns for its powerful divergence detection feature.
    It adheres to the final AiSignalPro architecture.
    """
    dependencies = ['zigzag'] # ✨ FIX: Correct dependency is 'zigzag'

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.k_period = int(self.params.get('k_period', 14))
        self.d_period = int(self.params.get('d_period', 3))
        self.smooth_k = int(self.params.get('smooth_k', 3))
        self.overbought = float(self.params.get('overbought', 80.0))
        self.oversold = float(self.params.get('oversold', 20.0))
        self.timeframe = self.params.get('timeframe', None)
        self.detect_divergence = bool(self.params.get('detect_divergence', True))
        self.zigzag_deviation = float(self.params.get('zigzag_deviation', 3.0))
        self.divergence_lookback = int(self.params.get('divergence_lookback', 5))
        
        suffix = f'_{self.k_period}_{self.d_period}_{self.smooth_k}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.k_col = f'stoch_k{suffix}'
        self.d_col = f'stoch_d{suffix}'

    def _calculate_stochastic(self, df: pd.DataFrame) -> pd.DataFrame:
        """The core, technically correct, and bias-free stochastic calculation logic."""
        res = pd.DataFrame(index=df.index)
        
        low_min = df['low'].rolling(window=self.k_period).min()
        high_max = df['high'].rolling(window=self.k_period).max()
        
        price_range = (high_max - low_min).replace(0, np.nan)
        
        fast_k = 100 * ((df['close'] - low_min) / price_range)
        
        res[self.k_col] = fast_k.rolling(window=self.smooth_k).mean()
        res[self.d_col] = res[self.k_col].rolling(window=self.d_period).mean()
            
        return res

    def calculate(self) -> 'StochasticIndicator':
        """
        ✨ FINAL ARCHITECTURE: No resampling. Just pure calculation.
        """
        df_for_calc = self.df

        if len(df_for_calc) < self.k_period + self.d_period + self.smooth_k:
            logger.warning(f"Not enough data for Stochastic on {self.timeframe or 'base'}.")
            self.df[self.k_col] = np.nan
            self.df[self.d_col] = np.nan
            return self

        stoch_results = self._calculate_stochastic(df_for_calc)
        
        self.df[self.k_col] = stoch_results[self.k_col]
        self.df[self.d_col] = stoch_results[self.d_col]
            
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
            price1, stoch1 = prev_pivot[price_col], prev_pivot[self.k_col]
            price2, stoch2 = last_pivot[price_col], last_pivot[self.k_col]
            if prev_pivot[pivot_col] == 1 and last_pivot[pivot_col] == 1:
                if price2 > price1 and stoch2 < stoch1: divergences.append({'type': 'Regular Bearish'})
                if price2 < price1 and stoch2 > stoch1: divergences.append({'type': 'Hidden Bearish'})
            elif prev_pivot[pivot_col] == -1 and last_pivot[pivot_col] == -1:
                if price2 < price1 and stoch2 > stoch1: divergences.append({'type': 'Regular Bullish'})
                if price2 > price1 and stoch2 < stoch1: divergences.append({'type': 'Hidden Bullish'})
        return divergences

    def analyze(self) -> Dict[str, Any]:
        """Provides a multi-faceted analysis of momentum and potential reversals."""
        valid_df = self.df.dropna(subset=[self.k_col, self.d_col])
        if len(valid_df) < 2: return {"status": "Insufficient Data"}
        
        last = valid_df.iloc[-1]; prev = valid_df.iloc[-2]
        k, d, prev_k, prev_d = last[self.k_col], last[self.d_col], prev[self.k_col], prev[self.d_col]
        
        position = "Neutral"
        if k > self.overbought and d > self.overbought: position = "Overbought"
        elif k < self.oversold and d < self.oversold: position = "Oversold"
        
        signal = "Hold"
        if prev_k <= prev_d and k > d:
            strength = "Strong" if k < self.oversold + 10 else "Normal"
            signal = f"{strength} Bullish Crossover"
        elif prev_k >= prev_d and k < d:
            strength = "Strong" if k > self.overbought - 10 else "Normal"
            signal = f"{strength} Bearish Crossover"
            
        k_slope = k - prev_k
        d_slope = d - prev_d
        divergences = self._find_divergences(valid_df)
        
        return {
            "status": "OK", "timeframe": self.timeframe or 'Base',
            "values": {"k": round(k, 2), "d": round(d, 2)},
            "analysis": {
                "position": position,
                "crossover_signal": signal,
                "momentum": {"k_slope": round(k_slope, 2), "d_slope": round(d_slope, 2)},
                "divergences": divergences
            }
        }
