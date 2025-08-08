import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

# اطمینان حاصل کنید که این اندیکاتورها از فایل‌های مربوطه و در نسخه‌های نهایی خود وارد شده‌اند
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class AdxIndicator(BaseIndicator):
    """
    ADX Indicator - Definitive, Complete, MTF & World-Class Version
    -----------------------------------------------------------------
    This is the final, unified version combining the full market structure
    analysis logic with the multi-timeframe (MTF) architectural pattern.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        # --- Parameters ---
        self.params = kwargs.get('params', {})
        self.period = int(self.params.get('period', 14))
        self.timeframe = self.params.get('timeframe', None)
        self.adx_thresholds = self.params.get('adx_thresholds', {
            'no_trend_max': 20,
            'weak_trend_max': 25,
            'strong_trend_max': 40
        })
        
        # --- Dynamic Column Naming ---
        suffix = f'_{self.period}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.adx_col = f'adx{suffix}'
        self.plus_di_col = f'plus_di{suffix}'
        self.minus_di_col = f'minus_di{suffix}'

    def calculate(self) -> 'AdxIndicator':
        """Calculates ADX, +DI, and -DI, handling MTF resampling and mapping internally."""
        base_df = self.df
        
        # ✨ MTF LOGIC: Resample data if a timeframe is specified
        if self.timeframe:
            if not isinstance(base_df.index, pd.DatetimeIndex):
                raise TypeError("DataFrame index must be a DatetimeIndex for MTF.")
            rules = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}
            calc_df = base_df.resample(self.timeframe).apply(rules).dropna()
        else:
            calc_df = base_df.copy()

        if len(calc_df) < self.period:
            logger.warning(f"Not enough data for ADX on timeframe {self.timeframe or 'base'}.")
            for col in [self.adx_col, self.plus_di_col, self.minus_di_col]:
                self.df[col] = np.nan
            return self

        # --- Vectorized Calculations on calc_df ---
        tr = pd.concat([
            calc_df['high'] - calc_df['low'],
            np.abs(calc_df['high'] - calc_df['close'].shift(1)),
            np.abs(calc_df['low'] - calc_df['close'].shift(1))
        ], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1/self.period, adjust=False).mean()

        move_up = calc_df['high'].diff()
        move_down = calc_df['low'].diff().mul(-1)

        plus_dm = np.where((move_up > move_down) & (move_up > 0), move_up, 0.0)
        minus_dm = np.where((move_down > move_up) & (move_down > 0), move_down, 0.0)

        plus_dm_smooth = pd.Series(plus_dm, index=calc_df.index).ewm(alpha=1/self.period, adjust=False).mean()
        minus_dm_smooth = pd.Series(minus_dm, index=calc_df.index).ewm(alpha=1/self.period, adjust=False).mean()
        
        safe_atr = atr.replace(0, np.nan)
        plus_di = (plus_dm_smooth / safe_atr) * 100
        minus_di = (minus_dm_smooth / safe_atr) * 100
        
        di_sum = (plus_di + minus_di).replace(0, np.nan)
        di_diff = np.abs(plus_di - minus_di)
        dx = (di_diff / di_sum) * 100
        adx = dx.ewm(alpha=1/self.period, adjust=False).mean()
        
        # --- Map results back to the original dataframe if MTF ---
        results_df = pd.DataFrame(index=calc_df.index)
        results_df[self.adx_col] = adx
        results_df[self.plus_di_col] = plus_di
        results_df[self.minus_di_col] = minus_di

        if self.timeframe:
            final_results = results_df.reindex(base_df.index, method='ffill')
            self.df[self.adx_col] = final_results[self.adx_col]
            self.df[self.plus_di_col] = final_results[self.plus_di_col]
            self.df[self.minus_di_col] = final_results[self.minus_di_col]
        else:
            self.df[self.adx_col] = results_df[self.adx_col]
            self.df[self.plus_di_col] = results_df[self.plus_di_col]
            self.df[self.minus_di_col] = results_df[self.minus_di_col]
            
        return self

    def analyze(self) -> Dict[str, Any]:
        """Provides a deep analysis of trend strength, direction, and momentum."""
        required_cols = [self.adx_col, self.plus_di_col, self.minus_di_col]
        valid_df = self.df.dropna(subset=required_cols)
        
        if len(valid_df) < 2:
            return {"status": "Insufficient Data", "timeframe": self.timeframe or 'Base'}
        
        last = valid_df.iloc[-1]
        prev = valid_df.iloc[-2]

        adx_val, plus_di, minus_di = last[self.adx_col], last[self.plus_di_col], last[self.minus_di_col]
        
        # --- Trend Strength Analysis ---
        t = self.adx_thresholds
        if adx_val <= t['no_trend_max']: strength = "No Trend"
        elif adx_val <= t['weak_trend_max']: strength = "Weak Trend"
        elif adx_val <= t['strong_trend_max']: strength = "Strong Trend"
        else: strength = "Very Strong Trend"
        
        is_strengthening = adx_val > prev[self.adx_col]

        # --- Direction & Crossover Analysis ---
        direction, cross_signal = "Neutral", "None"
        if plus_di > minus_di:
            direction = "Bullish"
            if prev[self.plus_di_col] <= prev[self.minus_di_col]: cross_signal = "Bullish Crossover"
        elif minus_di > plus_di:
            direction = "Bearish"
            if prev[self.minus_di_col] <= prev[self.plus_di_col]: cross_signal = "Bearish Crossover"

        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "values": {
                "adx": round(adx_val, 2),
                "plus_di": round(plus_di, 2),
                "minus_di": round(minus_di, 2),
            },
            "analysis": {
                "strength": strength,
                "direction": direction,
                "is_strengthening": is_strengthening,
                "cross_signal": cross_signal,
                "summary": f"{strength} ({direction}) - {'Strengthening' if is_strengthening else 'Weakening'}"
            }
        }
