# backend/engines/indicators/supertrend.py (v7.4 - The Final Polish)
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Tuple

from .base import BaseIndicator
from .utils import get_indicator_config_key

logger = logging.getLogger(__name__)

class SuperTrendIndicator(BaseIndicator):
    """
    SuperTrend - (v7.4 - The Final Polish)
    ------------------------------------------------------------------------
    This is the definitive, production-ready version. It incorporates all
    critical hotfixes for logic, logging, and dependency handling. The core
    calculation algorithm has also been slightly refactored for maximum
    clarity and efficiency. It is now fully robust and architecturally sound.
    """
    dependencies: list = ['atr']

    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], **kwargs):
        super().__init__(df, params=params, **kwargs)
        self.period = int(self.params.get('period', 10))
        self.multiplier = float(self.params.get('multiplier', 3.0))
        self.timeframe = self.params.get('timeframe')
        
        suffix = f'_{self.period}_{self.multiplier}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.supertrend_col = f'ST{suffix}'
        self.direction_col = f'ST_DIR{suffix}'
        
        self.atr_instance: BaseIndicator | None = None
        self.atr_col_name: str | None = None

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
            if np.isnan(prev_st):
                prev_st = final_lower_band[i-1] if direction[i-1] == 1 else final_upper_band[i-1]

            # ✅ FINAL POLISH (v7.4): Refactored for clarity, no redundant assignments.
            if final_upper_band[i] > prev_st and prev_close < prev_st:
                final_upper_band[i] = prev_st
            if final_lower_band[i] < prev_st and prev_close > prev_st:
                final_lower_band[i] = prev_st

            if close[i] > final_upper_band[i-1]: direction[i] = 1
            elif close[i] < final_lower_band[i-1]: direction[i] = -1
            else: direction[i] = direction[i-1]
            
            supertrend[i] = final_lower_band[i] if direction[i] == 1 else final_upper_band[i]
            
        return pd.Series(supertrend, index=df.index), pd.Series(direction, index=df.index)

    def calculate(self) -> 'SuperTrendIndicator':
        my_deps_config = self.params.get("dependencies", {})
        atr_order_params = my_deps_config.get('atr')
        if not atr_order_params:
            logger.error(f"[{self.__class__.__name__}] on {self.timeframe}: 'atr' dependency not defined."); return self
        
        atr_unique_key = get_indicator_config_key('atr', atr_order_params)
        self.atr_instance = self.dependencies.get(atr_unique_key)
        
        if not isinstance(self.atr_instance, BaseIndicator) or not hasattr(self.atr_instance, 'atr_col'):
            logger.warning(f"[{self.__class__.__name__}] on {self.timeframe}: missing or invalid ATR dependency '{atr_unique_key}'.")
            return self
        
        self.atr_col_name = self.atr_instance.atr_col
        if self.atr_col_name not in self.atr_instance.df.columns:
             logger.warning(f"[{self.__class__.__name__}] on {self.timeframe}: could not find ATR column '{self.atr_col_name}'.")
             return self
        
        df_for_calc = self.df.join(self.atr_instance.df[[self.atr_col_name]], how='left').dropna(subset=[self.atr_col_name])
        if len(df_for_calc) < self.period + 1:
            logger.warning(f"Not enough data for SuperTrend on {self.timeframe or 'base'}."); return self

        st_series, dir_series = self._calculate_supertrend(df_for_calc, self.multiplier, self.atr_col_name)
        
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
        if len(valid_df) < 5:
            return {"status": "Insufficient Data", **empty_analysis}
        
        last = valid_df.iloc[-1]; prev = valid_df.iloc[-2]
        
        # Correctly references the previous candle's direction
        last_dir, prev_dir = last[self.direction_col], prev[self.direction_col]
        
        trend = "Uptrend" if last_dir == 1 else "Downtrend"
        signal = "Trend Continuation"
        if last_dir == 1 and prev_dir == -1: signal = "Bullish Crossover"
        elif last_dir == -1 and prev_dir == 1: signal = "Bearish Crossover"
        
        st_slope = valid_df[self.supertrend_col].tail(5).diff().mean()
        is_exhausted = abs(st_slope) < (last[self.supertrend_col] * 0.0001)
        
        is_overextended = False
        if self.atr_col_name and self.atr_col_name in self.df.columns:
            atr_val = self.df[self.atr_col_name].iloc[-1]
            if atr_val is not None and not np.isnan(atr_val) and atr_val > 0:
                distance = abs(last['close'] - last[self.supertrend_col])
                is_overextended = distance > (atr_val * 2.5)
        else:
            logger.warning(f"[{self.__class__.__name__}] on {self.timeframe}: ATR column not found for 'overextended' check.")

        analysis_content = {
            "trend": trend, "signal": signal,
            "is_exhausted": is_exhausted, "is_overextended": is_overextended
        }
        values_content = {"supertrend_line": round(last[self.supertrend_col], 5)}
        
        return {
            "status": "OK", "timeframe": self.timeframe or 'Base',
            "values": values_content, "analysis": analysis_content
        }

