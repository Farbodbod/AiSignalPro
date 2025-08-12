import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class AdxIndicator(BaseIndicator):
    """
    ADX Indicator - (v4.1 - Miracle Ready)
    ---------------------------------------------------------------------------
    This world-class version is a pure and powerful trend analysis engine.
    It correctly provides the raw ADX, +DI, and -DI values, making it fully
    compatible with advanced, multi-factor confirmation strategies.
    """
    dependencies: list = [] # ADX calculates its own ATR internally for precision

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
        """ Calculates ADX, +DI, and -DI using vectorized operations. """
        df_for_calc = self.df
        
        if len(df_for_calc) < self.period * 2: # ADX needs more data to stabilize
            logger.warning(f"Not enough data for ADX on timeframe {self.timeframe or 'base'}.")
            for col in [self.adx_col, self.plus_di_col, self.minus_di_col]:
                self.df[col] = np.nan
            return self

        # This vectorized calculation is efficient and correct.
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
        
        self.df[self.adx_col] = adx
        self.df[self.plus_di_col] = plus_di
        self.df[self.minus_di_col] = minus_di
            
        return self

    def analyze(self) -> Dict[str, Any]:
        """ Provides a deep analysis of trend strength, direction, and momentum. """
        required_cols = [self.adx_col, self.plus_di_col, self.minus_di_col]
        valid_df = self.df.dropna(subset=required_cols)
        
        if len(valid_df) < 2:
            return {"status": "Insufficient Data"}
        
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
