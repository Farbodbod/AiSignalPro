import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Tuple, Optional

from .base import BaseIndicator
from .atr import AtrIndicator # We need to import this to call its static method

logger = logging.getLogger(__name__)

class SuperTrendIndicator(BaseIndicator):
    """
    SuperTrend - (v5.0 - Multi-Version Aware)
    ------------------------------------------------------------------------
    This world-class version is fully compatible with the IndicatorAnalyzer v9.0's
    Multi-Version Engine. It intelligently reads its dependency configuration
    to request the specific version of ATR it needs, ensuring a robust and
    error-free calculation process.
    """
    # ✅ MIRACLE UPGRADE: Dependency is now declared in config, not hardcoded here.
    dependencies: list = []

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.period = int(self.params.get('period', 10))
        self.multiplier = float(self.params.get('multiplier', 3.0))
        self.timeframe = self.params.get('timeframe', None)
        
        # ✅ MIRACLE UPGRADE: The indicator now reads its specific dependency config.
        # It defaults to a standard ATR(14) if not specified in config.
        self.atr_dependency_params = self.params.get('dependencies', {}).get('atr', {'period': 14})

        # Column names are based on this indicator's own unique parameters
        suffix = f'_{self.period}_{self.multiplier}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.supertrend_col = f'st{suffix}' # Shortened for clarity
        self.direction_col = f'st_dir{suffix}'
    
    def _calculate_supertrend(self, df: pd.DataFrame, multiplier: float, atr_col: str) -> Tuple[pd.Series, pd.Series]:
        """The core, optimized SuperTrend calculation logic using NumPy."""
        high = df['high'].to_numpy()
        low = df['low'].to_numpy()
        close = df['close'].to_numpy()
        atr = df[atr_col].to_numpy()

        # Calculation is vectorized for performance
        with np.errstate(invalid='ignore'):
            hl2 = (high + low) / 2
            final_upper_band = hl2 + (multiplier * atr)
            final_lower_band = hl2 - (multiplier * atr)
        
        supertrend = np.full(len(df), np.nan)
        direction = np.full(len(df), 1)

        for i in range(1, len(df)):
            # If the previous supertrend value is NaN, initialize it
            prev_st = supertrend[i-1] if not np.isnan(supertrend[i-1]) else final_lower_band[i-1]

            # Update final bands based on the previous supertrend value
            if final_upper_band[i] < prev_st or close[i-1] > prev_st:
                final_upper_band[i] = final_upper_band[i]
            else:
                final_upper_band[i] = prev_st

            if final_lower_band[i] > prev_st or close[i-1] < prev_st:
                final_lower_band[i] = final_lower_band[i]
            else:
                final_lower_band[i] = prev_st
                
            # Determine direction
            if close[i] > final_upper_band[i-1]:
                direction[i] = 1
            elif close[i] < final_lower_band[i-1]:
                direction[i] = -1
            else:
                direction[i] = direction[i-1]

            # Set the supertrend value based on the direction
            supertrend[i] = final_lower_band[i] if direction[i] == 1 else final_upper_band[i]

        return pd.Series(supertrend, index=df.index), pd.Series(direction, index=df.index)

    def calculate(self) -> 'SuperTrendIndicator':
        """ Calculates the SuperTrend using its required, specific version of ATR. """
        df_for_calc = self.df
        
        # SuperTrend needs at least its own period +1 for calculation
        if len(df_for_calc) < self.period + 1:
            logger.warning(f"Not enough data for SuperTrend on {self.timeframe or 'base'}.")
            self.df[self.supertrend_col] = np.nan
            self.df[self.direction_col] = np.nan
            return self

        # ✅ MIRACLE UPGRADE: Generates the required column name dynamically
        # based on its dependency's parameters, using the dependency's own static method.
        # This creates a robust, unbreakable contract between indicators.
        atr_col_name = AtrIndicator.get_col_name(self.atr_dependency_params, self.timeframe)
        
        if atr_col_name not in df_for_calc.columns:
            raise ValueError(f"Required ATR column '{atr_col_name}' not found for SuperTrend. Ensure ATR dependency is correctly configured.")
        
        st_series, dir_series = self._calculate_supertrend(df_for_calc, self.multiplier, atr_col_name)
        
        self.df[self.supertrend_col] = st_series
        self.df[self.direction_col] = dir_series
            
        return self

    def analyze(self) -> Dict[str, Any]:
        """Provides a bias-free analysis of the current trend and potential changes."""
        valid_df = self.df.dropna(subset=[self.supertrend_col, self.direction_col])
        if len(valid_df) < 2: return {"status": "Insufficient Data"}
        
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
