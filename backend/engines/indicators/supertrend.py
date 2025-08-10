import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Tuple

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class SuperTrendIndicator(BaseIndicator):
    """
    SuperTrend - Definitive, Optimized, MTF & World-Class Version (v4.0 - No Internal Deps)
    ---------------------------------------------------------------------------------------
    This version adheres to the final AiSignalPro architecture. It does not
    calculate its own dependencies. Instead, it consumes the pre-calculated ATR
    column provided by the IndicatorAnalyzer, making it a pure, efficient, and
    robust trend analysis engine.
    """
    dependencies = ['atr']

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.period = int(self.params.get('period', 10))
        self.multiplier = float(self.params.get('multiplier', 3.0))
        self.timeframe = self.params.get('timeframe', None)
        
        suffix = f'_{self.period}_{self.multiplier}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.supertrend_col = f'supertrend{suffix}'
        self.direction_col = f'supertrend_dir{suffix}'
    
    def _calculate_supertrend(self, df: pd.DataFrame, period: int, multiplier: float, atr_col: str) -> Tuple[pd.Series, pd.Series]:
        """The core, optimized SuperTrend calculation logic using NumPy."""
        high = df['high'].to_numpy(); low = df['low'].to_numpy(); close = df['close'].to_numpy()
        atr = df[atr_col].to_numpy()

        hl2 = (high + low) / 2
        final_upper_band = hl2 + (multiplier * atr)
        final_lower_band = hl2 - (multiplier * atr)
        
        supertrend = np.full(len(df), np.nan)
        direction = np.full(len(df), 1)

        for i in range(1, len(df)):
            if final_upper_band[i] > final_upper_band[i-1] or close[i-1] > final_upper_band[i-1]:
                final_upper_band[i] = final_upper_band[i-1]
            if final_lower_band[i] < final_lower_band[i-1] or close[i-1] < final_lower_band[i-1]:
                final_lower_band[i] = final_lower_band[i-1]

            if i > 0 and not np.isnan(supertrend[i-1]):
                if supertrend[i-1] == final_upper_band[i-1]:
                    direction[i] = -1 if close[i] < final_upper_band[i] else 1
                else:
                    direction[i] = 1 if close[i] > final_lower_band[i] else -1
            else: # Initial case
                 direction[i] = 1 if close[i] > final_lower_band[i] else -1

            supertrend[i] = final_lower_band[i] if direction[i] == 1 else final_upper_band[i]

        return pd.Series(supertrend, index=df.index), pd.Series(direction, index=df.index)

    def calculate(self) -> 'SuperTrendIndicator':
        """Calculates SuperTrend, assuming the ATR column is already present."""
        base_df = self.df
        if self.timeframe:
            if not isinstance(base_df.index, pd.DatetimeIndex): raise TypeError("DatetimeIndex required for MTF.")
            rules = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}
            calc_df = base_df.resample(self.timeframe, label='right', closed='right').apply(rules).dropna()
        else:
            calc_df = base_df.copy()

        if len(calc_df) < self.period:
            logger.warning(f"Not enough data for SuperTrend on {self.timeframe or 'base'}.")
            return self

        # ✨ THE MIRACLE FIX: Expect the ATR column to be pre-calculated.
        atr_col_name = f'atr_{self.period}'
        if self.timeframe: atr_col_name += f'_{self.timeframe}'
        
        if atr_col_name not in calc_df.columns:
            raise ValueError(f"Required ATR column '{atr_col_name}' not found for SuperTrend. Ensure ATR is calculated first by the Analyzer.")
        
        st_series, dir_series = self._calculate_supertrend(calc_df, self.period, self.multiplier, atr_col_name)
        
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
        """Provides a bias-free analysis of the current trend and potential changes."""
        valid_df = self.df.dropna(subset=[self.supertrend_col, self.direction_col])
        if len(valid_df) < 2: return {"status": "Insufficient Data", "analysis": {}}
        
        last = valid_df.iloc[-1]; prev = valid_df.iloc[-2]
        last_dir, prev_dir = last[self.direction_col], prev[self.direction_col]
        
        trend = "Uptrend" if last_dir == 1 else "Downtrend"
        signal = "Trend Continuation"
        if last_dir == 1 and prev_dir == -1: signal = "Bullish Crossover"
        elif last_dir == -1 and prev_dir == 1: signal = "Bearish Crossover"
        
        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "values": {"supertrend_line": round(last[self.supertrend_col], 5)},
            "analysis": {"trend": trend, "signal": signal}
        }
