import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Tuple

# اطمینان حاصل کنید که این اندیکاتورها از فایل‌های مربوطه و در نسخه‌های نهایی خود وارد شده‌اند
from .base import BaseIndicator
from .atr import AtrIndicator # نسخه کامل و نهایی MTF

logger = logging.getLogger(__name__)

class SuperTrendIndicator(BaseIndicator):
    """
    SuperTrend Indicator - Definitive, Optimized, MTF & World-Class Version
    --------------------------------------------------------------------------
    This is the final, unified version implementing the correct, non-repainting
    SuperTrend algorithm. It is highly optimized using NumPy and features the
    standardized MTF architecture for AiSignalPro.

    It can calculate the SuperTrend for any timeframe (e.g., 5m, 15m, 1H, 4H)
    on a base chart.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        # --- Parameters ---
        self.params = kwargs.get('params', {})
        self.period = int(self.params.get('period', 10))
        self.multiplier = float(self.params.get('multiplier', 3.0))
        self.timeframe = self.params.get('timeframe', None) # e.g., '5min', '15min', '1H', '4H'

        # --- Dynamic Column Naming ---
        suffix = f'_{self.period}_{self.multiplier}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.supertrend_col = f'supertrend{suffix}'
        self.direction_col = f'supertrend_dir{suffix}'
    
    def _calculate_supertrend(self, df: pd.DataFrame, period: int, multiplier: float) -> Tuple[pd.Series, pd.Series]:
        """The core, optimized SuperTrend calculation logic using NumPy."""
        if len(df) < period:
            logger.warning(f"Not enough data for SuperTrend (period={period}).")
            return pd.Series(np.nan, index=df.index), pd.Series(np.nan, index=df.index)

        # Dependency: Calculate ATR using our world-class AtrIndicator
        # Note: The AtrIndicator is called with the *same timeframe* implicitly.
        atr_indicator = AtrIndicator(df, params={'period': period, 'timeframe': None}) # No nested MTF
        df_with_atr = atr_indicator.calculate()
        atr_col = atr_indicator.atr_col
        
        if atr_col not in df_with_atr.columns or df_with_atr[atr_col].isnull().all():
            logger.error("ATR calculation failed, cannot proceed with SuperTrend.")
            return pd.Series(np.nan, index=df.index), pd.Series(np.nan, index=df.index)

        # --- NumPy Optimization ---
        high = df['high'].to_numpy()
        low = df['low'].to_numpy()
        close = df['close'].to_numpy()
        atr = df_with_atr[atr_col].to_numpy()

        hl2 = (high + low) / 2
        final_upper_band = hl2 + (multiplier * atr)
        final_lower_band = hl2 - (multiplier * atr)
        
        supertrend = np.full(len(df), np.nan)
        direction = np.full(len(df), 1) # Default to uptrend

        for i in range(1, len(df)):
            # If the current final upper band is greater than the previous one, or the previous close is greater, use the smaller value.
            if final_upper_band[i] > final_upper_band[i-1] or close[i-1] > final_upper_band[i-1]:
                final_upper_band[i] = final_upper_band[i-1]
            
            if final_lower_band[i] < final_lower_band[i-1] or close[i-1] < final_lower_band[i-1]:
                final_lower_band[i] = final_lower_band[i-1]

            # Determine trend direction
            if supertrend[i-1] == final_upper_band[i-1]:
                direction[i] = -1 if close[i] < final_upper_band[i] else 1
            else: # supertrend[i-1] == final_lower_band[i-1]
                direction[i] = 1 if close[i] > final_lower_band[i] else -1

            # Set the SuperTrend line value
            supertrend[i] = final_lower_band[i] if direction[i] == 1 else final_upper_band[i]

        return pd.Series(supertrend, index=df.index), pd.Series(direction, index=df.index)

    def calculate(self) -> 'SuperTrendIndicator':
        """Orchestrates the MTF calculation for SuperTrend."""
        base_df = self.df
        
        # ✨ MTF LOGIC: Resample data if a timeframe is specified
        if self.timeframe:
            if not isinstance(base_df.index, pd.DatetimeIndex):
                raise TypeError("DataFrame index must be a DatetimeIndex for MTF.")
            
            logger.info(f"Resampling data to {self.timeframe} for SuperTrend calculation.")
            rules = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}
            calc_df = base_df.resample(self.timeframe, label='right', closed='right').apply(rules).dropna()
        else:
            calc_df = base_df.copy()

        st_series, dir_series = self._calculate_supertrend(calc_df, self.period, self.multiplier)
        
        # --- Map results back to the original dataframe if MTF ---
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
        """Provides a clear analysis of the current trend and potential changes."""
        valid_df = self.df.dropna(subset=[self.supertrend_col, self.direction_col])
        if len(valid_df) < 2:
            return {"status": "Insufficient Data", "analysis": {}}

        last = valid_df.iloc[-1]
        prev = valid_df.iloc[-2]
        
        last_dir, prev_dir = last[self.direction_col], prev[self.direction_col]
        trend = "Uptrend" if last_dir == 1 else "Downtrend"
        
        signal = "Trend Continuation"
        if last_dir == 1 and prev_dir == -1: signal = "Bullish Crossover"
        elif last_dir == -1 and prev_dir == 1: signal = "Bearish Crossover"
        
        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "values": {
                "supertrend_line": round(last[self.supertrend_col], 5)
            },
            "analysis": {
                "trend": trend,
                "signal": signal
            }
        }
