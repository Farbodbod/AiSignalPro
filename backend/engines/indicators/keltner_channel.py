# backend/engines/indicators/keltner_channel.py (v7.0 - Logical Refactor)

import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Optional

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class KeltnerChannelIndicator(BaseIndicator):
    """
    Keltner Channel - (v7.0 - Logical Refactor)
    -----------------------------------------------------------------------------
    This version relies on the parent `IndicatorAnalyzer` to provide a complete
    DataFrame with all dependencies' data already present, removing the unsafe
    DataFrame join operation.
    """
    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], dependencies: Dict[str, BaseIndicator], **kwargs):
        super().__init__(df, params=params, dependencies=dependencies, **kwargs)
        self.ema_period = int(self.params.get('ema_period', 20))
        self.atr_multiplier = float(self.params.get('atr_multiplier', 2.0))
        self.timeframe = self.params.get('timeframe')
        self.squeeze_period = int(self.params.get('squeeze_period', 50))

        self.upper_col = 'KC_U'
        self.lower_col = 'KC_L'
        self.middle_col = 'KC_M'
        self.bandwidth_col = 'KC_BW'
        
        # Store the name of the ATR column from the dependency
        self.atr_col_name: Optional[str] = None

    def calculate(self) -> 'KeltnerChannelIndicator':
        atr_instance = self.dependencies.get('atr')
        if not isinstance(atr_instance, BaseIndicator) or atr_instance.df.empty:
            logger.warning(f"[{self.__class__.__name__}] on {self.timeframe} missing critical ATR dependency. Skipping calculation.")
            self.df[self.upper_col] = np.nan
            self.df[self.lower_col] = np.nan
            self.df[self.middle_col] = np.nan
            self.df[self.bandwidth_col] = np.nan
            return self

        atr_col_options = [col for col in atr_instance.df.columns if 'ATR' in col.upper()]
        if not atr_col_options:
            logger.warning(f"[{self.__class__.__name__}] on {self.timeframe} could not find ATR column in dependency dataframe.")
            self.df[self.upper_col] = np.nan
            self.df[self.lower_col] = np.nan
            self.df[self.middle_col] = np.nan
            self.df[self.bandwidth_col] = np.nan
            return self
        
        self.atr_col_name = atr_col_options[0]

        # ✅ FIX: Rely on the main DataFrame which has already been populated
        # by the IndicatorAnalyzer with the 'ATR' column.
        if self.atr_col_name not in self.df.columns:
            logger.warning(f"[{self.__class__.__name__}] on {self.timeframe} could not find '{self.atr_col_name}' in the main DataFrame. This indicates a prior calculation failure.")
            for col in [self.upper_col, self.lower_col, self.middle_col, self.bandwidth_col]:
                self.df[col] = np.nan
            return self
            
        required_data_length = max(self.ema_period, int(atr_instance.params.get('period', 10)))
        if len(self.df) < required_data_length:
            logger.warning(f"Not enough data for Keltner Channel on {self.timeframe or 'base'}.")
            for col in [self.upper_col, self.lower_col, self.middle_col, self.bandwidth_col]:
                self.df[col] = np.nan
            return self

        typical_price = (self.df['high'] + self.df['low'] + self.df['close']) / 3
        middle_band = typical_price.ewm(span=self.ema_period, adjust=False).mean()
        atr_value = self.df[self.atr_col_name] * self.atr_multiplier
        
        upper_band = middle_band + atr_value
        lower_band = middle_band - atr_value
        bandwidth = ((upper_band - lower_band) / middle_band.replace(0, np.nan)) * 100

        self.df[self.upper_col] = upper_band
        self.df[self.lower_col] = lower_band
        self.df[self.middle_col] = middle_band
        self.df[self.bandwidth_col] = bandwidth
        
        return self

    def analyze(self) -> Dict[str, Any]:
        required_cols = [self.upper_col, self.lower_col, self.middle_col, self.bandwidth_col, 'close']
        valid_df = self.df.dropna(subset=required_cols)
        
        if valid_df.empty:
            logger.warning(f"[{self.__class__.__name__}] on {self.timeframe} has an empty valid_df. Analysis aborted.")
            return {"status": "Insufficient Data"}

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
