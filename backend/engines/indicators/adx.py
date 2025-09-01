# backend/engines/indicators/adx.py (v5.0 - The Trend Quantum Engine)

import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, List

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class AdxIndicator(BaseIndicator):
    """
    ADX Indicator - (v5.0 - The Trend Quantum Engine)
    ---------------------------------------------------------------------------
    This quantum upgrade transforms the ADX indicator into a true trend analysis
    engine. Key enhancements include:
    
    1.  **Strategic Feature Addition:** Now provides a `series` output, containing
        recent ADX values. This is critical for advanced strategies that need to
        calculate "ADX delta" or trend acceleration.
        
    2.  **Full Architectural Alignment:** The architecture has been standardized
        to use the project's "Gold Standard" `default_config` pattern, and
        obsolete attributes have been removed, ensuring 100% compliance with
        the BaseIndicator v4.0+ framework.
        
    3.  **Enhanced Robustness:** Minor improvements to calculations and data
        validation have been implemented for maximum stability.
    """
    default_config: Dict[str, Any] = {
        'period': 14,
        'series_lookback': 5,
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
        self.adx_thresholds = self.params.get('adx_thresholds', self.default_config['adx_thresholds'])
        self.timeframe = self.params.get('timeframe')
        
        suffix = f'_{self.period}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        
        self.adx_col = f'adx{suffix}'
        self.plus_di_col = f'plus_di{suffix}'
        self.minus_di_col = f'minus_di{suffix}'

    def calculate(self) -> 'AdxIndicator':
        if len(self.df) < self.period * 2:
            logger.warning(f"Not enough data for ADX on timeframe {self.timeframe or 'base'}.")
            for col in [self.adx_col, self.plus_di_col, self.minus_di_col]:
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
        
        fill_limit = 3
        self.df[self.adx_col] = adx.ffill(limit=fill_limit)
        self.df[self.plus_di_col] = plus_di.ffill(limit=fill_limit)
        self.df[self.minus_di_col] = minus_di.ffill(limit=fill_limit)
            
        return self

    def analyze(self) -> Dict[str, Any]:
        required_cols = [self.adx_col, self.plus_di_col, self.minus_di_col]
        empty_analysis = {"values": {}, "analysis": {}, "series": []}

        if any(col not in self.df.columns for col in required_cols):
            return {"status": "Calculation Incomplete", **empty_analysis}

        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 2:
            return {"status": "Insufficient Data for Analysis", **empty_analysis}
        
        last = valid_df.iloc[-1]
        prev = valid_df.iloc[-2]

        adx_val, plus_di, minus_di = last[self.adx_col], last[self.plus_di_col], last[self.minus_di_col]
        
        t = self.adx_thresholds
        if adx_val <= t['no_trend_max']: strength = "No Trend"
        elif adx_val <= t['weak_trend_max']: strength = "Weak Trend"
        elif adx_val <= t['strong_trend_max']: strength = "Strong Trend"
        else: strength = "Very Strong Trend"
        
        is_strengthening = adx_val > prev[self.adx_col]

        direction, cross_signal = "Neutral", "None"
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
            "summary": f"{strength} ({direction}) - {'Strengthening' if is_strengthening else 'Weakening'}"
        }
        
        # ✅ STRATEGIC FEATURE: Provide a series of recent values for delta analysis
        series_content = [round(v, 2) for v in valid_df[self.adx_col].tail(self.series_lookback).tolist()]

        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "values": values_content,
            "analysis": analysis_content,
            "series": series_content
        }
