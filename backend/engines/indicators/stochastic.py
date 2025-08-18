# backend/engines/indicators/stochastic.py
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class StochasticIndicator(BaseIndicator):
    """
    Stochastic Oscillator - (v5.1 - Pure Calculation Engine)
    -----------------------------------------------------------------------------------
    This world-class version is a pure implementation of the Stochastic Oscillator.
    It has no external dependencies and serves as a foundational data provider.
    Divergence detection is correctly delegated to specialist indicators, adhering
    to the Single Responsibility Principle for maximum stability and modularity.
    """
    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], dependencies: Dict[str, BaseIndicator], **kwargs):
        super().__init__(df, params=params, dependencies=dependencies, **kwargs)
        self.k_period = int(self.params.get('k_period', 14))
        self.d_period = int(self.params.get('d_period', 3))
        self.smooth_k = int(self.params.get('smooth_k', 3))
        self.overbought = float(self.params.get('overbought', 80.0))
        self.oversold = float(self.params.get('oversold', 20.0))
        self.timeframe = self.params.get('timeframe')
        
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
        Calculates only the Stochastic values.
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
        
        return {
            "status": "OK", "timeframe": self.timeframe or 'Base',
            "values": {"k": round(k, 2), "d": round(d, 2)},
            "analysis": {
                "position": position,
                "crossover_signal": signal,
                "momentum": {"k_slope": round(k_slope, 2), "d_slope": round(d_slope, 2)},
                "divergences": [] # Returns an empty list as per the pure architecture
            }
        }
