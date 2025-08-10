import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Tuple

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class SuperTrendIndicator(BaseIndicator):
    """
    SuperTrend - Definitive, World-Class Version (v4.1 - Final Architecture)
    ------------------------------------------------------------------------
    This version adheres to the final AiSignalPro architecture. It performs its
    calculations on the pre-resampled dataframe provided by the IndicatorAnalyzer,
    making it a pure, efficient, and powerful trend analysis engine.
    """
    dependencies = ['atr']

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.period = int(self.params.get('period', 10))
        self.multiplier = float(self.params.get('multiplier', 3.0))
        self.timeframe = self.params.get('timeframe', None)
        
        # Note: The ATR period for SuperTrend is typically the same as the SuperTrend period.
        # We will use self.period to construct the expected ATR column name.
        self.atr_period = int(self.params.get('atr_period', self.period))

        suffix = f'_{self.period}_{self.multiplier}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.supertrend_col = f'supertrend{suffix}'
        self.direction_col = f'supertrend_dir{suffix}'
    
    def _calculate_supertrend(self, df: pd.DataFrame, period: int, multiplier: float, atr_col: str) -> Tuple[pd.Series, pd.Series]:
        """The core, optimized SuperTrend calculation logic using NumPy."""
        high = df['high'].to_numpy(); low = df['low'].to_numpy(); close = df['close'].to_numpy()
        atr = df[atr_col].to_numpy()

        # Calculation can produce NaNs if ATR is NaN, handle this.
        with np.errstate(invalid='ignore'):
            hl2 = (high + low) / 2
            final_upper_band = hl2 + (multiplier * atr)
            final_lower_band = hl2 - (multiplier * atr)
        
        supertrend = np.full(len(df), np.nan)
        direction = np.full(len(df), 1)

        for i in range(1, len(df)):
            # If previous supertrend is NaN, initialize based on current close vs lower band
            prev_st = supertrend[i-1]
            if np.isnan(prev_st):
                prev_st = final_lower_band[i-1] # A reasonable starting point

            if final_upper_band[i] > prev_st or close[i-1] > prev_st:
                final_upper_band[i] = min(final_upper_band[i], prev_st)
            
            if final_lower_band[i] < prev_st or close[i-1] < prev_st:
                final_lower_band[i] = max(final_lower_band[i], prev_st)

            if close[i] > final_upper_band[i-1]:
                direction[i] = 1
            elif close[i] < final_lower_band[i-1]:
                direction[i] = -1
            else:
                direction[i] = direction[i-1]

            supertrend[i] = final_lower_band[i] if direction[i] == 1 else final_upper_band[i]

        return pd.Series(supertrend, index=df.index), pd.Series(direction, index=df.index)

    def calculate(self) -> 'SuperTrendIndicator':
        """
        ✨ FINAL ARCHITECTURE: No resampling. Just pure calculation.
        """
        df_for_calc = self.df
        
        if len(df_for_calc) < self.period:
            logger.warning(f"Not enough data for SuperTrend on {self.timeframe or 'base'}.")
            self.df[self.supertrend_col] = np.nan
            self.df[self.direction_col] = np.nan
            return self

        atr_col_name = f'atr_{self.atr_period}'
        if self.timeframe: atr_col_name += f'_{self.timeframe}'
        
        if atr_col_name not in df_for_calc.columns:
            raise ValueError(f"Required ATR column '{atr_col_name}' not found for SuperTrend. Ensure ATR is calculated first by the Analyzer.")
        
        st_series, dir_series = self._calculate_supertrend(df_for_calc, self.period, self.multiplier, atr_col_name)
        
        self.df[self.supertrend_col] = st_series
        self.df[self.direction_col] = dir_series
            
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
