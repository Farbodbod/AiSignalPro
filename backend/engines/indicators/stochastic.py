# backend/engines/indicators/stochastic.py (v6.0 - The Quantum Momentum Edition)
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Optional

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class StochasticIndicator(BaseIndicator):
    """
    Stochastic Oscillator - (v6.0 - The Quantum Momentum Edition)
    -----------------------------------------------------------------------------------
    This world-class version evolves into a quantum momentum engine. It provides
    granular zone analysis, a structured signal output with strength, and is built
    on a fully standardized, multi-instance-safe, and Sentinel-compliant
    architecture for flawless integration and maximum analytical depth.
    """
    dependencies: list = []

    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], **kwargs):
        super().__init__(df, params=params, **kwargs)
        self.k_period = int(self.params.get('k_period', 14))
        self.d_period = int(self.params.get('d_period', 3))
        self.smooth_k = int(self.params.get('smooth_k', 3))
        self.timeframe = self.params.get('timeframe')
        
        # Thresholds are now more granular
        self.overbought = float(self.params.get('overbought', 80.0))
        self.oversold = float(self.params.get('oversold', 20.0))
        self.bullish_zone_min = float(self.params.get('bullish_zone_min', 50.0))
        self.bearish_zone_max = float(self.params.get('bearish_zone_max', 50.0))

        # ✅ FINAL STANDARD: Dynamic and conflict-proof column naming.
        suffix = f'_{self.k_period}_{self.d_period}_{self.smooth_k}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        else: suffix += '_base'
        self.k_col = f'stoch_k{suffix}'
        self.d_col = f'stoch_d{suffix}'

    def calculate(self) -> 'StochasticIndicator':
        if len(self.df) < self.k_period + self.d_period + self.smooth_k:
            logger.warning(f"Not enough data for Stochastic on {self.timeframe or 'base'}.")
            self.df[self.k_col] = np.nan
            self.df[self.d_col] = np.nan
            return self

        low_min = self.df['low'].rolling(window=self.k_period).min()
        high_max = self.df['high'].rolling(window=self.k_period).max()
        
        price_range = (high_max - low_min).replace(0, np.nan)
        fast_k = 100 * ((self.df['close'] - low_min) / price_range)
        
        k_series = fast_k.rolling(window=self.smooth_k).mean()
        d_series = k_series.rolling(window=self.d_period).mean()

        # ✅ HARDENED FILL: Add a limited ffill to prevent NaN propagation.
        fill_limit = 3
        self.df[self.k_col] = k_series.ffill(limit=fill_limit).bfill(limit=2)
        self.df[self.d_col] = d_series.ffill(limit=fill_limit).bfill(limit=2)
        return self
    
    def analyze(self) -> Dict[str, Any]:
        required_cols = [self.k_col, self.d_col]
        empty_analysis = {"values": {}, "analysis": {}}
        if not all(col in self.df.columns for col in required_cols):
            return {"status": "Calculation Incomplete", **empty_analysis}

        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 2: 
            return {"status": "Insufficient Data", **empty_analysis}
        
        last = valid_df.iloc[-1]; prev = valid_df.iloc[-2]
        k, d, prev_k, prev_d = last[self.k_col], last[self.d_col], prev[self.k_col], prev[self.d_col]
        
        # ✅ QUANTUM MOMENTUM ANALYSIS: Granular zone detection.
        position = "Neutral"
        if k > self.overbought and d > self.overbought: position = "Extreme Overbought"
        elif k < self.oversold and d < self.oversold: position = "Extreme Oversold"
        elif k > self.bullish_zone_min and d > self.bullish_zone_min: position = "Bullish Zone"
        elif k < self.bearish_zone_max and d < self.bearish_zone_max: position = "Bearish Zone"
        
        # ✅ HYPER-INTELLIGENT SIGNAL: Structured signal output with strength.
        signal_obj = {"type": "Hold", "direction": "Neutral", "strength": "Neutral"}
        if prev_k <= prev_d and k > d: # Bullish Cross
            signal_obj["type"] = "Crossover"
            signal_obj["direction"] = "Bullish"
            signal_obj["strength"] = "Strong" if prev_k < self.oversold else "Normal"
        elif prev_k >= prev_d and k < d: # Bearish Cross
            signal_obj["type"] = "Crossover"
            signal_obj["direction"] = "Bearish"
            signal_obj["strength"] = "Strong" if prev_k > self.overbought else "Normal"
            
        k_slope = k - prev_k; d_slope = d - prev_d
        
        values_content = {"k": round(k, 2), "d": round(d, 2)}
        analysis_content = {
            "position": position,
            "crossover_signal": signal_obj,
            "momentum": {"k_slope": round(k_slope, 2), "d_slope": round(d_slope, 2)},
            "divergences": [] # Delegated to specialist indicators
        }
        
        return {
            "status": "OK", "timeframe": self.timeframe or 'Base',
            "values": values_content,
            "analysis": analysis_content
        }
