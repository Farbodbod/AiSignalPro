# backend/engines/indicators/adx.py (v4.3 - Hardened Fill Edition)

import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class AdxIndicator(BaseIndicator):
    """
    ADX Indicator - (v4.3 - Hardened Fill Edition)
    ---------------------------------------------------------------------------
    This world-class version is hardened against NaN propagation by replacing
    unlimited forward-fills with a safer, limited ffill. This prevents stale
    data from contaminating the series during periods of poor data quality.
    The output structure is also hardened to be fully "Sentinel Compliant".
    """
    dependencies: list = []

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.period = int(self.params.get('period', 14))
        self.timeframe = self.params.get('timeframe', None)
        self.adx_thresholds = self.params.get('adx_thresholds', {
            'no_trend_max': 20, 'weak_trend_max': 25, 'strong_trend_max': 40
        })
        
        suffix = f'_{self.period}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.adx_col = f'adx{suffix}'
        self.plus_di_col = f'plus_di{suffix}'
        self.minus_di_col = f'minus_di{suffix}'

    def calculate(self) -> 'AdxIndicator':
        df_for_calc = self.df
        
        if len(df_for_calc) < self.period * 2:
            logger.warning(f"Not enough data for ADX on timeframe {self.timeframe or 'base'}.")
            for col in [self.adx_col, self.plus_di_col, self.minus_di_col]:
                self.df[col] = np.nan
            return self

        tr = pd.concat([
            df_for_calc['high'] - df_for_calc['low'],
            abs(df_for_calc['high'] - df_for_calc['close'].shift(1)),
            abs(df_for_calc['low'] - df_for_calc['close'].shift(1))
        ], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1/self.period, adjust=False).mean()

        move_up = df_for_calc['high'].diff()
        move_down = df_for_calc['low'].diff().mul(-1)

        plus_dm = np.where((move_up > move_down) & (move_up > 0), move_up, 0.0)
        minus_dm = np.where((move_down > move_up) & (move_down > 0), move_down, 0.0)

        plus_dm_smooth = pd.Series(plus_dm, index=df_for_calc.index).ewm(alpha=1/self.period, adjust=False).mean()
        minus_dm_smooth = pd.Series(minus_dm, index=df_for_calc.index).ewm(alpha=1/self.period, adjust=False).mean()
        
        safe_atr = atr.replace(0, np.nan)
        plus_di = (plus_dm_smooth / safe_atr) * 100
        minus_di = (minus_dm_smooth / safe_atr) * 100
        
        di_sum = (plus_di + minus_di).replace(0, np.nan)
        di_diff = abs(plus_di - minus_di)
        dx = (di_diff / di_sum) * 100
        adx = dx.ewm(alpha=1/self.period, adjust=False).mean()
        
        # ✅ HARDENED FILL (v4.3): Use a limited forward-fill to prevent stale data propagation.
        fill_limit = 3 # Allow filling for a maximum of 3 consecutive bad candles.
        self.df[self.adx_col] = adx.ffill(limit=fill_limit)
        self.df[self.plus_di_col] = plus_di.ffill(limit=fill_limit)
        self.df[self.minus_di_col] = minus_di.ffill(limit=fill_limit)
            
        return self

    def analyze(self) -> Dict[str, Any]:
        required_cols = [self.adx_col, self.plus_di_col, self.minus_di_col]
        empty_analysis = {"values": {}, "analysis": {}}

        if any(col not in self.df.columns for col in required_cols):
            return {"status": "Calculation Incomplete - Columns missing", **empty_analysis}

        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 2:
            return {"status": "Insufficient Data", **empty_analysis}
        
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

        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "values": values_content,
            "analysis": analysis_content
        }
