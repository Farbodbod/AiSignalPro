# backend/engines/indicators/keltner_channel.py
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

from .base import BaseIndicator
from .utils import get_indicator_config_key # ✅ World-Class Practice: Import from shared utils

logger = logging.getLogger(__name__)

class KeltnerChannelIndicator(BaseIndicator):
    """
    Keltner Channel - (v6.2 - Definitive Dependency Hotfix)
    -----------------------------------------------------------------------------
    This version contains the definitive, world-class fix for dependency lookup.
    It now correctly reconstructs the unique_key of its dependency (ATR) from
    its own configuration, ensuring a flawless and robust connection to the
    data provider. It also includes the guard clause to prevent KeyErrors.
    """
    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], dependencies: Dict[str, BaseIndicator], **kwargs):
        super().__init__(df, params=params, dependencies=dependencies, **kwargs)
        self.ema_period = int(self.params.get('ema_period', 20))
        self.atr_multiplier = float(self.params.get('atr_multiplier', 2.0))
        self.timeframe = self.params.get('timeframe')
        self.squeeze_period = int(self.params.get('squeeze_period', 50))
        self.upper_col, self.lower_col, self.middle_col, self.bandwidth_col = 'KC_U', 'KC_L', 'KC_M', 'KC_BW'

    def calculate(self) -> 'KeltnerChannelIndicator':
        """ 
        Calculates Keltner Channels by correctly looking up its ATR dependency instance.
        """
        # ✅ DEFINITIVE FIX: The correct way to look up a dependency.
        my_deps_config = self.params.get("dependencies", {})
        atr_order_params = my_deps_config.get('atr')
        if not atr_order_params:
            logger.error(f"[{self.__class__.__name__}] on {self.timeframe} cannot run: 'atr' dependency not defined in config.")
            return self
        
        atr_unique_key = get_indicator_config_key('atr', atr_order_params)
        atr_instance = self.dependencies.get(atr_unique_key)
        
        if not isinstance(atr_instance, BaseIndicator):
            logger.warning(f"[{self.__class__.__name__}] on {self.timeframe} missing critical ATR instance ('{atr_unique_key}'). Skipping.")
            return self

        atr_df = atr_instance.df
        atr_col_options = [col for col in atr_df.columns if 'ATR' in col.upper()]
        if not atr_col_options:
            logger.warning(f"[{self.__class__.__name__}] on {self.timeframe} could not find ATR column in dependency.")
            return self
        atr_col_name = atr_col_options[0]
        
        self.df = self.df.join(atr_df[[atr_col_name]], how='left')
        atr_period = int(atr_instance.params.get('period', 10))

        if len(self.df) < max(self.ema_period, atr_period):
            return self

        typical_price = (self.df['high'] + self.df['low'] + self.df['close']) / 3
        middle_band = typical_price.ewm(span=self.ema_period, adjust=False).mean()
        atr_value = self.df[atr_col_name].dropna() * self.atr_multiplier
        
        self.df[self.upper_col] = middle_band + atr_value
        self.df[self.lower_col] = middle_band - atr_value
        self.df[self.bandwidth_col] = ((self.df[self.upper_col] - self.df[self.lower_col]) / middle_band.replace(0, np.nan)) * 100
        
        return self

    def analyze(self) -> Dict[str, Any]:
        """ 
        Provides deep analysis of price action relative to the Keltner Channel.
        """
        required_cols = [self.upper_col, self.lower_col, self.middle_col, self.bandwidth_col]
        if not all(col in self.df.columns for col in required_cols):
            return {"status": "Calculation Incomplete - Required columns missing"}

        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < self.squeeze_period:
            return {"status": "Insufficient Data"}

        last = valid_df.iloc[-1]
        close, upper, middle, lower = last['close'], last[self.upper_col], last[self.middle_col], last[self.lower_col]
        
        position = "Inside Channel"
        if close > upper: position = "Breakout Above"
        elif close < lower: position = "Breakdown Below"
            
        recent_bandwidth = valid_df[self.bandwidth_col].tail(self.squeeze_period)
        is_in_squeeze = last[self.bandwidth_col] <= recent_bandwidth.min()
        
        return {
            "status": "OK", "timeframe": self.timeframe or 'Base',
            "values": {"upper_band": round(upper, 5), "middle_band": round(middle, 5), "lower_band": round(lower, 5), "bandwidth_percent": round(last[self.bandwidth_col], 2)},
            "analysis": {"position": position, "is_in_squeeze": is_in_squeeze}
        }
