# backend/engines/indicators/stochastic.py
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, List

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class StochasticIndicator(BaseIndicator):
    """
    Stochastic Oscillator - (v5.0 - Dependency Injection Native)
    -----------------------------------------------------------------------------------
    This world-class version is re-engineered to natively support the Dependency
    Injection (DI) architecture. The core Stochastic calculation and analysis remain
    untouched, while the optional divergence detection feature now robustly consumes
    the ZigZag instance, making the entire indicator flawless and decoupled.
    """
    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], dependencies: Dict[str, BaseIndicator], **kwargs):
        super().__init__(df, params=params, dependencies=dependencies, **kwargs)
        self.k_period = int(self.params.get('k_period', 14))
        self.d_period = int(self.params.get('d_period', 3))
        self.smooth_k = int(self.params.get('smooth_k', 3))
        self.overbought = float(self.params.get('overbought', 80.0))
        self.oversold = float(self.params.get('oversold', 20.0))
        self.timeframe = self.params.get('timeframe')
        self.detect_divergence = bool(self.params.get('detect_divergence', True))
        self.divergence_lookback = int(self.params.get('divergence_lookback', 5))
        
        # Simplified, robust, and locally-scoped column names.
        self.k_col = 'STOCH_K'
        self.d_col = 'STOCH_D'

    def _calculate_stochastic(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        The core, technically correct, and bias-free stochastic calculation logic.
        This function's internal algorithm is 100% preserved.
        """
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
        Calculates only the Stochastic values. ZigZag data is handled in the analyze phase.
        """
        if len(self.df) < self.k_period + self.d_period + self.smooth_k:
            logger.warning(f"Not enough data for Stochastic on {self.timeframe or 'base'}.")
            self.df[self.k_col] = np.nan
            self.df[self.d_col] = np.nan
            return self

        stoch_results = self._calculate_stochastic(self.df)
        
        self.df[self.k_col] = stoch_results[self.k_col]
        self.df[self.d_col] = stoch_results[self.d_col]
            
        return self
    
    def _find_divergences(self, stoch_df: pd.DataFrame) -> List[Dict[str, Any]]:
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
        
        analysis_df = stoch_df.join(zigzag_df[[pivot_col, price_col]], how='left')
        analysis_df[self.k_col] = analysis_df[self.k_col].ffill()
        
        pivots_df = analysis_df[analysis_df[pivot_col] != 0].dropna(subset=[self.k_col])
        if len(pivots_df) < 2: 
            return []
        
        last_pivot = pivots_df.iloc[-1]
        previous_pivots = pivots_df.iloc[-self.divergence_lookback:-1]
        divergences = []
        for i in range(len(previous_pivots)):
            prev_pivot = previous_pivots.iloc[i]
            price1, stoch1 = prev_pivot[price_col], prev_pivot[self.k_col]
            price2, stoch2 = last_pivot[price_col], last_pivot[self.k_col]
            if prev_pivot[pivot_col] == 1 and last_pivot[pivot_col] == 1: # Two peaks
                if price2 > price1 and stoch2 < stoch1: divergences.append({'type': 'Regular Bearish'})
                if price2 < price1 and stoch2 > stoch1: divergences.append({'type': 'Hidden Bearish'})
            elif prev_pivot[pivot_col] == -1 and last_pivot[pivot_col] == -1: # Two troughs
                if price2 < price1 and stoch2 > stoch1: divergences.append({'type': 'Regular Bullish'})
                if price2 > price1 and stoch2 < stoch1: divergences.append({'type': 'Hidden Bullish'})
        return divergences

    def analyze(self) -> Dict[str, Any]:
        """
        Provides a multi-faceted analysis of momentum and potential reversals.
        The core analysis logic is 100% preserved.
        """
        valid_df = self.df.dropna(subset=[self.k_col, self.d_col])
        if len(valid_df) < 2: 
            return {"status": "Insufficient Data"}
        
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
