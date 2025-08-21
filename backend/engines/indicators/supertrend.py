# backend/engines/indicators/supertrend.py (v7.0 - The Dynamic Engine)
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Tuple

from .base import BaseIndicator
from .utils import get_indicator_config_key

logger = logging.getLogger(__name__)

class SuperTrendIndicator(BaseIndicator):
    """
    SuperTrend - (v7.0 - The Dynamic Engine)
    ------------------------------------------------------------------------
    This definitive, world-class version evolves into a dynamic analysis
    engine. It features dynamic column naming to support multiple instances,
    a hardened NaN-fill logic for ultimate stability, and an enhanced analysis
    method that now detects 'Trend Exhaustion' and 'Overextended' states.
    """
    dependencies: list = ['atr']

    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], **kwargs):
        super().__init__(df, params=params, **kwargs)
        self.period = int(self.params.get('period', 10))
        self.multiplier = float(self.params.get('multiplier', 3.0))
        self.timeframe = self.params.get('timeframe')
        
        # ✅ DYNAMIC ARCHITECTURE: Column names are now based on parameters
        suffix = f'_{self.period}_{self.multiplier}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.supertrend_col = f'ST{suffix}'
        self.direction_col = f'ST_DIR{suffix}'

    def _calculate_supertrend(self, df: pd.DataFrame, multiplier: float, atr_col: str) -> Tuple[pd.Series, pd.Series]:
        high, low, close, atr = df['high'].to_numpy(), df['low'].to_numpy(), df['close'].to_numpy(), df[atr_col].to_numpy()
        with np.errstate(invalid='ignore'):
            hl2 = (high + low) / 2
            final_upper_band = hl2 + (multiplier * atr)
            final_lower_band = hl2 - (multiplier * atr)
        
        supertrend = np.full(len(df), np.nan); direction = np.full(len(df), 1)
        
        for i in range(1, len(df)):
            prev_close = close[i-1]
            prev_st = supertrend[i-1]
            
            # If previous ST is NaN, initialize it for the first calculation step
            if np.isnan(prev_st):
                prev_st = final_lower_band[i-1] if direction[i-1] == 1 else final_upper_band[i-1]

            # UPPER BAND
            if final_upper_band[i] < prev_st or prev_close > prev_st:
                final_upper_band[i] = final_upper_band[i]
            else:
                final_upper_band[i] = prev_st

            # LOWER BAND
            if final_lower_band[i] > prev_st or prev_close < prev_st:
                final_lower_band[i] = final_lower_band[i]
            else:
                final_lower_band[i] = prev_st

            # DIRECTION
            if close[i] > final_upper_band[i-1]: direction[i] = 1
            elif close[i] < final_lower_band[i-1]: direction[i] = -1
            else: direction[i] = direction[i-1]
            
            supertrend[i] = final_lower_band[i] if direction[i] == 1 else final_upper_band[i]
            
        return pd.Series(supertrend, index=df.index), pd.Series(direction, index=df.index)

    def calculate(self) -> 'SuperTrendIndicator':
        my_deps_config = self.params.get("dependencies", {})
        atr_order_params = my_deps_config.get('atr')
        if not atr_order_params:
            logger.error(f"[{self.name}] on {self.timeframe}: 'atr' dependency not defined."); return self
        
        atr_unique_key = get_indicator_config_key('atr', atr_order_params)
        atr_instance = self.dependencies.get(atr_unique_key)
        if not isinstance(atr_instance, BaseIndicator):
            logger.warning(f"[{self.name}] on {self.timeframe}: missing ATR dependency '{atr_unique_key}'."); return self

        atr_col_options = [col for col in atr_instance.df.columns if col.startswith('atr_')]
        if not atr_col_options:
            logger.warning(f"[{self.name}] on {self.timeframe}: could not find ATR column."); return self
        atr_col_name = atr_col_options[0]
        
        df_for_calc = self.df.join(atr_instance.df[[atr_col_name]], how='left').dropna(subset=[atr_col_name])
        if len(df_for_calc) < self.period + 1:
            logger.warning(f"Not enough data for SuperTrend on {self.timeframe or 'base'}."); return self

        st_series, dir_series = self._calculate_supertrend(df_for_calc, self.multiplier, atr_col_name)
        
        # ✅ HARDENED FILL (v7.0): Use a limited forward-fill.
        fill_limit = 3
        self.df[self.supertrend_col] = st_series.ffill(limit=fill_limit)
        self.df[self.direction_col] = dir_series.ffill(limit=fill_limit)
        return self

    def analyze(self) -> Dict[str, Any]:
        required_cols = [self.supertrend_col, self.direction_col]
        empty_analysis = {"values": {}, "analysis": {}}
        if not all(col in self.df.columns for col in required_cols):
            return {"status": "Calculation Incomplete", **empty_analysis}

        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 5: # Need a few candles for slope/exhaustion
            return {"status": "Insufficient Data", **empty_analysis}
        
        last = valid_df.iloc[-1]; prev = valid_df.iloc[-2]
        last_dir, prev_dir = last[self.direction_col], prev[self.direction_col]
        
        trend = "Uptrend" if last_dir == 1 else "Downtrend"
        signal = "Trend Continuation"
        if last_dir == 1 and prev_dir == -1: signal = "Bullish Crossover"
        elif last_dir == -1 and prev_dir == 1: signal = "Bearish Crossover"
        
        # ✅ HYPER-INTELLIGENT ANALYSIS (v7.0):
        # Trend Exhaustion Check (flat line)
        st_slope = valid_df[self.supertrend_col].tail(5).diff().mean()
        is_exhausted = abs(st_slope) < (last[self.supertrend_col] * 0.0001) # Slope is less than 0.01% of price
        
        # Overextended Check (price far from line)
        distance = abs(last['close'] - last[self.supertrend_col])
        atr_val = self.df[next((c for c in self.df.columns if c.startswith('atr_')), None)].iloc[-1]
        is_overextended = atr_val is not None and distance > (atr_val * 2.5)

        analysis_content = {
            "trend": trend, "signal": signal,
            "is_exhausted": is_exhausted, "is_overextended": is_overextended
        }
        values_content = {"supertrend_line": round(last[self.supertrend_col], 5)}
        
        return {
            "status": "OK", "timeframe": self.timeframe or 'Base',
            "values": values_content, "analysis": analysis_content
        }

