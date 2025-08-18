# backend/engines/indicators/keltner_channel.py
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class KeltnerChannelIndicator(BaseIndicator):
    """
    Keltner Channel - (v6.1 - KeyError Hotfix)
    -----------------------------------------------------------------------------
    This version includes a critical hotfix in the analyze() method. A guard
    clause has been added to prevent a fatal KeyError when the calculate() method
    exits early (e.g., due to missing dependencies or insufficient data),
    ensuring the indicator fails gracefully instead of crashing the analysis phase.
    """
    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], dependencies: Dict[str, BaseIndicator], **kwargs):
        super().__init__(df, params=params, dependencies=dependencies, **kwargs)
        self.ema_period = int(self.params.get('ema_period', 20))
        self.atr_multiplier = float(self.params.get('atr_multiplier', 2.0))
        self.timeframe = self.params.get('timeframe')
        self.squeeze_period = int(self.params.get('squeeze_period', 50))

        # Simplified, robust, and locally-scoped column names.
        self.upper_col = 'KC_U'
        self.lower_col = 'KC_L'
        self.middle_col = 'KC_M'
        self.bandwidth_col = 'KC_BW'

    def calculate(self) -> 'KeltnerChannelIndicator':
        """ 
        Calculates Keltner Channels by directly consuming its ATR dependency instance.
        """
        atr_instance = self.dependencies.get('atr')
        if not atr_instance:
            logger.warning(f"[{self.__class__.__name__}] on {self.timeframe} missing critical ATR dependency. Skipping calculation.")
            return self

        atr_df = atr_instance.df
        atr_col_options = [col for col in atr_df.columns if 'ATR' in col.upper()]
        if not atr_col_options:
            logger.warning(f"[{self.__class__.__name__}] on {self.timeframe} could not find ATR column in dependency dataframe.")
            return self
        atr_col_name = atr_col_options[0]
        
        self.df = self.df.join(atr_df[[atr_col_name]], how='left')
        atr_period = int(atr_instance.params.get('period', 10))

        if len(self.df) < max(self.ema_period, atr_period):
            logger.warning(f"Not enough data for Keltner Channel on {self.timeframe or 'base'}.")
            # Do not create columns if there's not enough data
            return self

        typical_price = (self.df['high'] + self.df['low'] + self.df['close']) / 3
        middle_band = typical_price.ewm(span=self.ema_period, adjust=False).mean()
        atr_value = self.df[atr_col_name] * self.atr_multiplier
        
        upper_band = middle_band + atr_value
        lower_band = middle_band - atr_value
        bandwidth = ((upper_band - lower_band) / middle_band.replace(0, np.nan)) * 100

        self.df[self.upper_col] = upper_band
        self.df[self.lower_col] = lower_band
        self.df[self.middle_col] = middle_band
        self.df[self.bandwidth_col] = bandwidth
        
        return self

    def analyze(self) -> Dict[str, Any]:
        """ 
        Provides deep analysis of price action relative to the Keltner Channel.
        """
        # ✅ KEY FIX: Add a guard clause to prevent KeyError if calculate() exited early.
        required_cols = [self.upper_col, self.lower_col, self.middle_col, self.bandwidth_col]
        if not all(col in self.df.columns for col in required_cols):
            return {"status": "Calculation Incomplete - Required columns missing"}

        valid_df = self.df.dropna(subset=required_cols)
        
        if len(valid_df) < self.squeeze_period:
            return {"status": "Insufficient Data"}

        last = valid_df.iloc[-1]
        close = last['close']
        upper, middle, lower = last[self.upper_col], last[self.middle_col], last[self.lower_col]
        
        position = "Inside Channel"
        if close > upper: position = "Breakout Above"
        elif close < lower: position = "Breakdown Below"
            
        recent_bandwidth = valid_df[self.bandwidth_col].tail(self.squeeze_period)
        is_in_squeeze = last[self.bandwidth_col] <= recent_bandwidth.min()
        
        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "values": {
                "upper_band": round(upper, 5),
                "middle_band": round(middle, 5),
                "lower_band": round(lower, 5),
                "bandwidth_percent": round(last[self.bandwidth_col], 2)
            },
            "analysis": {
                "position": position,
                "is_in_squeeze": is_in_squeeze
            }
        }
