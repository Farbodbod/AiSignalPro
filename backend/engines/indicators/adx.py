# backend/engines/indicators/adx.py (v6.0 - The Adaptive Regime Engine)

import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, List

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class AdxIndicator(BaseIndicator):
    """
    ADX Indicator - (v6.0 - The Adaptive Regime Engine)
    ---------------------------------------------------------------------------
    This quantum leap transforms the ADX into a self-adapting regime detection
    engine. Instead of relying on fixed thresholds (e.g., 25), it now calculates
    the percentile rank of the current ADX value against its own historical
    distribution. This allows strategies to make smarter, context-aware decisions
    that automatically adapt to each asset's unique volatility profile.

    🚀 KEY EVOLUTIONS in v6.0:
    1.  **ADX Percentile Rank:** The core innovation. The indicator now calculates
        and outputs the 'adx_percentile', a value from 0-100 indicating the
        strength of the current trend relative to its recent history.
    2.  **Configurable Lookback:** Introduces a 'regime_lookback_period' to
        control the sample size for statistical analysis.
    
    (All features from v5.0, including `series` output, are preserved).
    """
    default_config: Dict[str, Any] = {
        'period': 14,
        'series_lookback': 5,
        'regime_lookback_period': 200, # Lookback for statistical percentile ranking
        'adx_thresholds': {
            'no_trend_max': 20,
            'weak_trend_max': 25,
            'strong_trend_max': 40
        }
    }

    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], **kwargs):
        super().__init__(df, params=params, **kwargs)
        self.period = int(self.params.get('period', self.default_config['period']))
        self.series_lookback = int(self.params.get('series_lookback', self.default_config['series_lookback']))
        self.regime_lookback_period = int(self.params.get('regime_lookback_period', self.default_config['regime_lookback_period']))
        self.adx_thresholds = self.params.get('adx_thresholds', self.default_config['adx_thresholds'])
        self.timeframe = self.params.get('timeframe')
        
        suffix = f'_{self.period}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        
        self.adx_col = f'adx{suffix}'
        self.plus_di_col = f'plus_di{suffix}'
        self.minus_di_col = f'minus_di{suffix}'
        self.adx_percentile_col = f'adx_pct{suffix}' # New column for the percentile

    def calculate(self) -> 'AdxIndicator':
        min_data_needed = max(self.period * 2, self.regime_lookback_period)
        if len(self.df) < min_data_needed:
            logger.warning(f"Not enough data for ADX on timeframe {self.timeframe or 'base'}. Need {min_data_needed}, have {len(self.df)}.")
            for col in [self.adx_col, self.plus_di_col, self.minus_di_col, self.adx_percentile_col]:
                self.df[col] = np.nan
            return self

        high_minus_low = self.df['high'] - self.df['low']
        high_minus_prev_close = abs(self.df['high'] - self.df['close'].shift(1))
        low_minus_prev_close = abs(self.df['low'] - self.df['close'].shift(1))
        
        tr = pd.concat([high_minus_low, high_minus_prev_close, low_minus_prev_close], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1/self.period, adjust=False).mean()

        move_up = self.df['high'].diff()
        move_down = self.df['low'].diff().mul(-1)

        plus_dm = np.where((move_up > move_down) & (move_up > 0), move_up, 0.0)
        minus_dm = np.where((move_down > move_up) & (move_down > 0), move_down, 0.0)

        plus_dm_smooth = pd.Series(plus_dm, index=self.df.index).ewm(alpha=1/self.period, adjust=False).mean()
        minus_dm_smooth = pd.Series(minus_dm, index=self.df.index).ewm(alpha=1/self.period, adjust=False).mean()
        
        safe_atr = atr.replace(0, 1e-9)
        plus_di = (plus_dm_smooth / safe_atr) * 100
        minus_di = (minus_dm_smooth / safe_atr) * 100
        
        di_sum = (plus_di + minus_di).replace(0, 1e-9)
        di_diff = abs(plus_di - minus_di)
        dx = (di_diff / di_sum) * 100
        adx = dx.ewm(alpha=1/self.period, adjust=False).mean()
        
        # ✅ QUANTUM UPGRADE: Calculate the percentile rank of the current ADX value
        self.df[self.adx_percentile_col] = adx.rolling(
            window=self.regime_lookback_period,
            min_periods=int(self.regime_lookback_period / 2)
        ).rank(pct=True) * 100
        
        fill_limit = 3
        self.df[self.adx_col] = adx.ffill(limit=fill_limit)
        self.df[self.plus_di_col] = plus_di.ffill(limit=fill_limit)
        self.df[self.minus_di_col] = minus_di.ffill(limit=fill_limit)
        self.df[self.adx_percentile_col] = self.df[self.adx_percentile_col].ffill(limit=fill_limit)
            
        return self

    def analyze(self) -> Dict[str, Any]:
        required_cols = [self.adx_col, self.plus_di_col, self.minus_di_col, self.adx_percentile_col]
        empty_analysis = {"values": {}, "analysis": {}, "series": []}

        if any(col not in self.df.columns for col in required_cols):
            return {"status": "Calculation Incomplete", **empty_analysis}

        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 2:
            return {"status": "Insufficient Data for Analysis", **empty_analysis}
        
        last = valid_df.iloc[-1]
        prev = valid_df.iloc[-2]

        adx_val = last[self.adx_col]
        plus_di = last[self.plus_di_col]
        minus_di = last[self.minus_di_col]
        adx_percentile = last[self.adx_percentile_col]
        
        t = self.adx_thresholds
        if adx_val <= t['no_trend_max']: strength = "No Trend"
        elif adx_val <= t['weak_trend_max']: strength = "Weak Trend"
        elif adx_val <= t['strong_trend_max']: strength = "Strong Trend"
        else: strength = "Very Strong Trend"
        
        is_strengthening = adx_val > prev[self.adx_col]

        direction = "Neutral"
        cross_signal = "None"
        if plus_di > minus_di:
            direction = "Bullish"
            if prev[self.plus_di_col] <= prev[self.minus_di_col]: cross_signal = "Bullish Crossover"
        elif minus_di > plus_di:
            direction = "Bearish"
            if prev[self.minus_di_col] <= prev[self.plus_di_col]: cross_signal = "Bearish Crossover"

        values_content = {
            "adx": round(adx_val, 2),
            "plus_di": round(plus_di, 2),
            "minus_di": round(minus_di, 2),
        }

        analysis_content = {
            "strength": strength,
            "direction": direction,
            "is_strengthening": is_strengthening,
            "cross_signal": cross_signal,
            "summary": f"{strength} ({direction}) - {'Strengthening' if is_strengthening else 'Weakening'}",
            "adx_percentile": round(adx_percentile, 2) # ✅ QUANTUM UPGRADE: Add percentile to output
        }
        
        series_content = [round(v, 2) for v in valid_df[self.adx_col].tail(self.series_lookback).tolist()]

        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "values": values_content,
            "analysis": analysis_content,
            "series": series_content
        }
