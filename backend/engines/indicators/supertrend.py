# backend/engines/indicators/supertrend.py
import pandas as pd
import numpy as np
import logging
import json
from typing import Dict, Any, Tuple

from .base import BaseIndicator
from .utils import get_indicator_config_key # ✅ World-Class Practice: Import from shared utils

logger = logging.getLogger(__name__)

class SuperTrendIndicator(BaseIndicator):
    """
    SuperTrend - (v6.3 - Unified Utils)
    ------------------------------------------------------------------------
    This definitive version is fully DI-native and hardened. It no longer contains
    a local copy of the helper functions, instead importing them from the shared
    `utils.py` module, adhering to the DRY principle and professional software
    engineering standards. All logic is 100% preserved.
    """
    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], dependencies: Dict[str, BaseIndicator], **kwargs):
        super().__init__(df, params=params, dependencies=dependencies, **kwargs)
        self.period = int(self.params.get('period', 10))
        self.multiplier = float(self.params.get('multiplier', 3.0))
        self.timeframe = self.params.get('timeframe')
        self.supertrend_col = 'ST'
        self.direction_col = 'ST_DIR'
    
    def _calculate_supertrend(self, df: pd.DataFrame, multiplier: float, atr_col: str) -> Tuple[pd.Series, pd.Series]:
        """
        The core, optimized SuperTrend calculation logic using NumPy.
        This function's internal algorithm is 100% preserved.
        """
        high = df['high'].to_numpy(); low = df['low'].to_numpy()
        close = df['close'].to_numpy(); atr = df[atr_col].to_numpy()
        with np.errstate(invalid='ignore'):
            hl2 = (high + low) / 2
            final_upper_band = hl2 + (multiplier * atr)
            final_lower_band = hl2 - (multiplier * atr)
        supertrend = np.full(len(df), np.nan); direction = np.full(len(df), 1)
        for i in range(1, len(df)):
            prev_st = supertrend[i-1] if not np.isnan(supertrend[i-1]) else final_lower_band[i-1]
            if final_upper_band[i] < prev_st or close[i-1] > prev_st: final_upper_band[i] = final_upper_band[i]
            else: final_upper_band[i] = prev_st
            if final_lower_band[i] > prev_st or close[i-1] < prev_st: final_lower_band[i] = final_lower_band[i]
            else: final_lower_band[i] = prev_st
            if close[i] > final_upper_band[i-1]: direction[i] = 1
            elif close[i] < final_lower_band[i-1]: direction[i] = -1
            else: direction[i] = direction[i-1]
            supertrend[i] = final_lower_band[i] if direction[i] == 1 else final_upper_band[i]
        return pd.Series(supertrend, index=df.index), pd.Series(direction, index=df.index)

    def calculate(self) -> 'SuperTrendIndicator':
        """ 
        Calculates the SuperTrend by correctly looking up its ATR dependency instance.
        """
        my_deps_config = self.params.get("dependencies", {})
        atr_order_params = my_deps_config.get('atr')
        if not atr_order_params:
            logger.error(f"[{self.__class__.__name__}] on {self.timeframe} cannot run: 'atr' dependency is not defined in its config.")
            return self
        
        atr_unique_key = get_indicator_config_key('atr', atr_order_params)
        atr_instance = self.dependencies.get(atr_unique_key)
        
        if not isinstance(atr_instance, BaseIndicator):
            logger.warning(f"[{self.__class__.__name__}] on {self.timeframe} missing critical ATR dependency instance ('{atr_unique_key}'). Calculation skipped.")
            return self

        atr_df = atr_instance.df
        atr_col_options = [col for col in atr_df.columns if 'ATR' in col.upper()]
        if not atr_col_options:
            logger.warning(f"[{self.__class__.__name__}] on {self.timeframe} could not find ATR column in dependency. Calculation skipped.")
            return self
        atr_col_name = atr_col_options[0]
        
        self.df = self.df.join(atr_df[[atr_col_name]], how='left')

        if len(self.df) < self.period + 1:
            logger.warning(f"Not enough data for SuperTrend on {self.timeframe or 'base'}. Calculation skipped.")
            return self

        st_series, dir_series = self._calculate_supertrend(self.df.dropna(subset=[atr_col_name]), self.multiplier, atr_col_name)
        
        self.df[self.supertrend_col] = st_series
        self.df[self.direction_col] = dir_series
            
        return self

    def analyze(self) -> Dict[str, Any]:
        """
        Provides a bias-free analysis of the current trend and potential changes.
        """
        required_cols = [self.supertrend_col, self.direction_col]
        if not all(col in self.df.columns for col in required_cols):
            return {"status": "Calculation Incomplete - Required columns missing"}

        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 2: 
            return {"status": "Insufficient Data"}
        
        last, prev = valid_df.iloc[-1], valid_df.iloc[-2]
        last_dir, prev_dir = last[self.direction_col], prev[self.direction_col]
        
        trend = "Uptrend" if last_dir == 1 else "Downtrend"
        signal = "Trend Continuation"
        if last_dir == 1 and prev_dir == -1: 
            signal = "Bullish Crossover"
        elif last_dir == -1 and prev_dir == 1: 
            signal = "Bearish Crossover"
        
        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "values": {"supertrend_line": round(last[self.supertrend_col], 5)},
            "analysis": {"trend": trend, "signal": signal}
        }
