import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Tuple
from .base import BaseIndicator
from .atr import AtrIndicator

logger = logging.getLogger(__name__)

class SuperTrendIndicator(BaseIndicator):
    """ SuperTrend Indicator - Definitive, Optimized, MTF & World-Class Version (v3.1 - Bugfix) """
    def __init__(self, df: pd.DataFrame, **kwargs):
        # ... (بخش init بدون تغییر باقی می‌ماند) ...
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.period = int(self.params.get('period', 10))
        self.multiplier = float(self.params.get('multiplier', 3.0))
        self.timeframe = self.params.get('timeframe', None)
        suffix = f'_{self.period}_{self.multiplier}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.supertrend_col = f'supertrend{suffix}'
        self.direction_col = f'supertrend_dir{suffix}'
    
    def _calculate_supertrend(self, df: pd.DataFrame, period: int, multiplier: float) -> Tuple[pd.Series, pd.Series]:
        if len(df) < period:
            logger.warning(f"Not enough data for SuperTrend (period={period}).")
            return pd.Series(np.nan, index=df.index), pd.Series(np.nan, index=df.index)

        # ✨ FIX: Correctly handle the return from AtrIndicator.calculate()
        atr_instance = AtrIndicator(df, params={'period': period, 'timeframe': None}).calculate()
        df_with_atr = atr_instance.df
        atr_col = atr_instance.atr_col
        
        if atr_col not in df_with_atr.columns or df_with_atr[atr_col].isnull().all():
            logger.error("ATR calculation failed, cannot proceed with SuperTrend.")
            return pd.Series(np.nan, index=df.index), pd.Series(np.nan, index=df.index)

        # ... (بخش بهینه‌سازی شده با NumPy بدون تغییر باقی می‌ماند) ...
        high = df['high'].to_numpy(); low = df['low'].to_numpy(); close = df['close'].to_numpy()
        atr = df_with_atr[atr_col].to_numpy()
        hl2 = (high + low) / 2
        final_upper_band = hl2 + (multiplier * atr); final_lower_band = hl2 - (multiplier * atr)
        supertrend = np.full(len(df), np.nan); direction = np.full(len(df), 1)
        for i in range(1, len(df)):
            if final_upper_band[i] > final_upper_band[i-1] or close[i-1] > final_upper_band[i-1]: final_upper_band[i] = final_upper_band[i-1]
            if final_lower_band[i] < final_lower_band[i-1] or close[i-1] < final_lower_band[i-1]: final_lower_band[i] = final_lower_band[i-1]
            if supertrend[i-1] == final_upper_band[i-1]: direction[i] = -1 if close[i] < final_upper_band[i] else 1
            else: direction[i] = 1 if close[i] > final_lower_band[i] else -1
            supertrend[i] = final_lower_band[i] if direction[i] == 1 else final_upper_band[i]
        return pd.Series(supertrend, index=df.index), pd.Series(direction, index=df.index)

    def calculate(self) -> 'SuperTrendIndicator':
        # ... (بخش calculate بدون تغییر باقی می‌ماند) ...
        base_df = self.df
        if self.timeframe:
            if not isinstance(base_df.index, pd.DatetimeIndex): raise TypeError("DatetimeIndex required for MTF.")
            rules = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}
            calc_df = base_df.resample(self.timeframe, label='right', closed='right').apply(rules).dropna()
        else: calc_df = base_df.copy()
        st_series, dir_series = self._calculate_supertrend(calc_df, self.period, self.multiplier)
        results_df = pd.DataFrame(index=calc_df.index)
        results_df[self.supertrend_col] = st_series
        results_df[self.direction_col] = dir_series
        if self.timeframe:
            final_results = results_df.reindex(base_df.index, method='ffill')
            self.df[self.supertrend_col] = final_results[self.supertrend_col]
            self.df[self.direction_col] = final_results[self.direction_col]
        else:
            self.df[self.supertrend_col] = results_df[self.supertrend_col]
            self.df[self.direction_col] = results_df[self.direction_col]
        return self

    def analyze(self) -> Dict[str, Any]:
        # ... (بخش analyze کامل و بدون تغییر است) ...
        valid_df = self.df.dropna(subset=[self.supertrend_col, self.direction_col])
        if len(valid_df) < 2: return {"status": "Insufficient Data", "analysis": {}}
        last = valid_df.iloc[-1]; prev = valid_df.iloc[-2]
        last_dir, prev_dir = last[self.direction_col], prev[self.direction_col]
        trend = "Uptrend" if last_dir == 1 else "Downtrend"
        signal = "Trend Continuation"
        if last_dir == 1 and prev_dir == -1: signal = "Bullish Crossover"
        elif last_dir == -1 and prev_dir == 1: signal = "Bearish Crossover"
        return { "status": "OK", "timeframe": self.timeframe or 'Base', "values": {"supertrend_line": round(last[self.supertrend_col], 5)}, "analysis": {"trend": trend, "signal": signal} }
