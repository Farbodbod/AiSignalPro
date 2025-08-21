# backend/engines/indicators/keltner_channel.py (v7.0 - The Dynamic Engine)
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

from .base import BaseIndicator
from .utils import get_indicator_config_key

logger = logging.getLogger(__name__)

class KeltnerChannelIndicator(BaseIndicator):
    """
    Keltner Channel - (v7.0 - The Dynamic Engine)
    -----------------------------------------------------------------------------
    This world-class version introduces a dynamic architecture with parameter-based
    column naming and a precision dependency link to ATR. It is also hardened
    with a Sentinel-compliant output structure, making it a fully robust,
    modular, and multi-instance-safe component for all strategies.
    """
    dependencies: list = ['atr']

    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], **kwargs):
        super().__init__(df, params=params, **kwargs)
        self.ema_period = int(self.params.get('ema_period', 20))
        self.atr_multiplier = float(self.params.get('atr_multiplier', 2.0))
        self.timeframe = self.params.get('timeframe')
        self.squeeze_period = int(self.params.get('squeeze_period', 50))
        
        # ✅ DYNAMIC ARCHITECTURE: Column names are now based on parameters
        atr_period = int(self.params.get("dependencies", {}).get("atr", {}).get('period', 10))
        suffix = f'_{self.ema_period}_{self.atr_multiplier}_{atr_period}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        
        self.upper_col = f'KC_U{suffix}'
        self.lower_col = f'KC_L{suffix}'
        self.middle_col = f'KC_M{suffix}'
        self.bandwidth_col = f'KC_BW{suffix}'

    def calculate(self) -> 'KeltnerChannelIndicator':
        my_deps_config = self.params.get("dependencies", {})
        atr_order_params = my_deps_config.get('atr')
        if not atr_order_params:
            logger.error(f"[{self.name}] on {self.timeframe}: 'atr' dependency not defined.")
            return self
        
        atr_unique_key = get_indicator_config_key('atr', atr_order_params)
        atr_instance = self.dependencies.get(atr_unique_key)
        
        if not isinstance(atr_instance, BaseIndicator) or not hasattr(atr_instance, 'atr_col'):
            logger.warning(f"[{self.name}] on {self.timeframe}: missing or invalid ATR instance ('{atr_unique_key}').")
            return self
        
        # ✅ PRECISION DEPENDENCY LINKING: Directly use the column name from the ATR instance.
        atr_col_name = atr_instance.atr_col
        if atr_col_name not in atr_instance.df.columns:
             logger.warning(f"[{self.name}] on {self.timeframe}: could not find ATR column '{atr_col_name}'.")
             return self
        
        df_for_calc = self.df.join(atr_instance.df[[atr_col_name]], how='left')
        atr_period = int(atr_instance.params.get('period', 10))

        if len(df_for_calc) < max(self.ema_period, atr_period):
            logger.warning(f"Not enough data for Keltner Channel on {self.timeframe or 'base'}.")
            return self

        typical_price = (df_for_calc['high'] + df_for_calc['low'] + df_for_calc['close']) / 3
        middle_band = typical_price.ewm(span=self.ema_period, adjust=False).mean()
        atr_value = df_for_calc[atr_col_name].dropna() * self.atr_multiplier
        
        upper_band = middle_band + atr_value
        lower_band = middle_band - atr_value
        
        self.df[self.upper_col] = upper_band
        self.df[self.lower_col] = lower_band
        self.df[self.middle_col] = middle_band
        self.df[self.bandwidth_col] = ((self.df[self.upper_col] - self.df[self.lower_col]) / self.df[self.middle_col].replace(0, np.nan)) * 100
        
        return self

    def analyze(self) -> Dict[str, Any]:
        required_cols = [self.upper_col, self.lower_col, self.middle_col, self.bandwidth_col]
        empty_analysis = {"values": {}, "analysis": {}}
        if not all(col in self.df.columns for col in required_cols):
            return {"status": "Calculation Incomplete", **empty_analysis}

        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < self.squeeze_period:
            return {"status": "Insufficient Data", **empty_analysis}

        last = valid_df.iloc[-1]
        close, upper, middle, lower = last['close'], last[self.upper_col], last[self.middle_col], last[self.lower_col]
        position = "Inside Channel"
        if close > upper: position = "Breakout Above"
        elif close < lower: position = "Breakdown Below"
        
        recent_bandwidth = valid_df[self.bandwidth_col].tail(self.squeeze_period)
        is_in_squeeze = last[self.bandwidth_col] <= recent_bandwidth.min()
        
        values_content = {"upper_band": round(upper, 5), "middle_band": round(middle, 5), "lower_band": round(lower, 5), "bandwidth_percent": round(last[self.bandwidth_col], 2)}
        analysis_content = {"position": position, "is_in_squeeze": is_in_squeeze}
        
        return {
            "status": "OK", "timeframe": self.timeframe or 'Base',
            "values": values_content,
            "analysis": analysis_content
        }
