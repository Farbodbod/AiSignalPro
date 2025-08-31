# backend/engines/indicators/cci.py (v6.0 - The Momentum Engine)
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, List

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class CciIndicator(BaseIndicator):
    """
    CCI Indicator - (v6.0 - The Momentum Engine)
    --------------------------------------------------------------------------
    This quantum upgrade transforms the CCI from a senior analyst into a true
    Momentum Engine. Key architectural and analytical enhancements include:

    1.  **Momentum Acceleration Analysis:** The core innovation. The indicator now
        calculates the slope of the CCI over a short lookback period to determine
        the true state of momentum (e.g., 'Accelerating Bullish', 
        'Decelerating Bearish'), providing predictive insight, not just lagging data.

    2.  **Refactored Event-Driven Output:** The flawed, self-overwriting text signal
        is replaced by a clean, robust system of boolean flags (e.g., 
        'is_bullish_cross', 'is_entering_overbought'). This provides strategies with
        precise, non-conflicting triggers.

    3.  **Dual-Lookback Intelligence:** It uses a long lookback (e.g., 200 bars)
        for stable, adaptive threshold calculation (market character) and a short
        lookback (e.g., 5 bars) for instantaneous momentum analysis (market velocity).

    4.  **Unified & Compatible Output:** The output structure is streamlined by
        consolidating all analysis into a single 'analysis' object and adding a
        'series' key to provide recent values for dependent strategies.
    """
    dependencies: list = []
    
    default_config: Dict[str, Any] = {
        'period': 20,
        'constant': 0.015,
        'use_adaptive_thresholds': True,
        'adaptive_lookback': 200,
        'adaptive_multiplier': 2.0,
        'adaptive_min_level': 100.0,
        'momentum_lookback': 5,
        'fixed_overbought': 100.0,
        'fixed_oversold': -100.0,
        'extreme_overbought': 200.0,
        'extreme_oversold': -200.0,
    }

    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], **kwargs):
        super().__init__(df, params=params, **kwargs)
        self.period = int(self.params.get('period', self.default_config['period']))
        self.constant = float(self.params.get('constant', self.default_config['constant']))
        self.use_adaptive_thresholds = bool(self.params.get('use_adaptive_thresholds', self.default_config['use_adaptive_thresholds']))
        self.adaptive_lookback = int(self.params.get('adaptive_lookback', self.default_config['adaptive_lookback']))
        self.adaptive_multiplier = float(self.params.get('adaptive_multiplier', self.default_config['adaptive_multiplier']))
        self.adaptive_min_level = float(self.params.get('adaptive_min_level', self.default_config['adaptive_min_level']))
        self.momentum_lookback = int(self.params.get('momentum_lookback', self.default_config['momentum_lookback']))
        self.fixed_overbought = float(self.params.get('overbought', self.default_config['fixed_overbought']))
        self.fixed_oversold = float(self.params.get('oversold', self.default_config['fixed_oversold']))
        self.extreme_overbought = float(self.params.get('extreme_overbought', self.default_config['extreme_overbought']))
        self.extreme_oversold = float(self.params.get('extreme_oversold', self.default_config['extreme_oversold']))
        self.timeframe = self.params.get('timeframe')
        
        suffix = f'_{self.period}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.cci_col = f'cci{suffix}'

    def calculate(self) -> 'CciIndicator':
        if len(self.df) < self.period:
            logger.warning(f"Not enough data for CCI on {self.timeframe or 'base'}.")
            self.df[self.cci_col] = np.nan
            return self

        tp = (self.df['high'] + self.df['low'] + self.df['close']) / 3
        ma_tp = tp.rolling(window=self.period).mean()
        mean_dev = tp.rolling(window=self.period).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
        
        safe_denominator = (self.constant * mean_dev).replace(0, 1e-9) # Avoid division by zero
        cci_series = (tp - ma_tp) / safe_denominator
        
        self.df[self.cci_col] = cci_series
        return self

    def analyze(self) -> Dict[str, Any]:
        empty_analysis = {"values": {}, "analysis": {}, "series": []}
        if self.cci_col not in self.df.columns or self.df[self.cci_col].isnull().all():
            return {"status": "Calculation Incomplete", **empty_analysis}

        valid_cci = self.df[self.cci_col].dropna()
        if len(valid_cci) < self.momentum_lookback:
            return {"status": "Insufficient Data for Analysis", **empty_analysis}
        
        last_val = valid_cci.iloc[-1]
        prev_val = valid_cci.iloc[-2]
        
        # --- 1. Threshold Calculation (Long-term lookback) ---
        if self.use_adaptive_thresholds and len(valid_cci) >= self.adaptive_lookback:
            cci_std = valid_cci.tail(self.adaptive_lookback).std()
            overbought_level = max(cci_std * self.adaptive_multiplier, self.adaptive_min_level)
            oversold_level = -overbought_level
            threshold_type = "Adaptive"
        else:
            overbought_level = self.fixed_overbought
            oversold_level = self.fixed_oversold
            threshold_type = "Fixed"

        # --- 2. Position and Event Flag Analysis (Clean & Non-Conflicting) ---
        position = "Neutral"
        if last_val > self.extreme_overbought: position = "Extreme Overbought"
        elif last_val < self.extreme_oversold: position = "Extreme Oversold"
        elif last_val > overbought_level: position = "Overbought"
        elif last_val < oversold_level: position = "Oversold"
        
        analysis = {
            "position": position,
            "is_bullish_cross": prev_val <= oversold_level and last_val > oversold_level,
            "is_bearish_cross": prev_val >= overbought_level and last_val < overbought_level,
            "is_entering_overbought": prev_val < overbought_level and last_val >= overbought_level,
            "is_entering_oversold": prev_val > oversold_level and last_val <= oversold_level,
            "is_in_extreme_buy": last_val > self.extreme_overbought,
            "is_in_extreme_sell": last_val < self.extreme_oversold,
            "threshold_type": threshold_type,
            "overbought_level": round(overbought_level, 2),
            "oversold_level": round(oversold_level, 2)
        }

        # --- 3. Momentum Acceleration Analysis (Short-term lookback) ---
        recent_series = valid_cci.tail(self.momentum_lookback).values
        if len(recent_series) == self.momentum_lookback:
            x = np.arange(len(recent_series))
            slope = np.polyfit(x, recent_series, 1)[0]
            
            analysis["momentum_slope"] = round(slope, 2)
            
            if slope > 0.5: # Threshold for significant positive slope
                analysis["momentum_state"] = "Accelerating Bullish" if last_val > prev_val else "Decelerating Bearish"
            elif slope < -0.5: # Threshold for significant negative slope
                analysis["momentum_state"] = "Accelerating Bearish" if last_val < prev_val else "Decelerating Bullish"
            else:
                analysis["momentum_state"] = "Neutral"
        else:
            analysis["momentum_slope"] = None
            analysis["momentum_state"] = "Unknown"

        # --- 4. Final Output Assembly ---
        values_content = {"cci": round(last_val, 2)}
        series_content = [round(v, 2) for v in valid_cci.tail(self.momentum_lookback).tolist()]

        return {
            "status": "OK",
            "timeframe": self.timeframe or "Base",
            "values": values_content,
            "analysis": analysis,
            "series": series_content
        }
