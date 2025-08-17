# backend/engines/indicators/chandelier_exit.py (v6.0 - Logical Refactor)

import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Optional

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class ChandelierExitIndicator(BaseIndicator):
    """
    Chandelier Exit - (v6.0 - Logical Refactor)
    -----------------------------------------------------------------------------
    This version relies on the parent `IndicatorAnalyzer` to provide a complete
    DataFrame with all dependencies' data already present, removing the unsafe
    DataFrame join operation.
    """
    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], dependencies: Dict[str, BaseIndicator], **kwargs):
        super().__init__(df, params=params, dependencies=dependencies, **kwargs)
        self.atr_multiplier = float(self.params.get('atr_multiplier', 3.0))
        self.timeframe = self.params.get('timeframe')
        
        # Determine the ATR period from the dependency or a default value
        atr_instance = self.dependencies.get('atr')
        if atr_instance and isinstance(atr_instance, BaseIndicator):
            self.atr_period = int(atr_instance.params.get('period', 22))
            self.atr_col_name: Optional[str] = [col for col in atr_instance.df.columns if 'ATR' in col.upper()][0]
        else:
            self.atr_period = 22
            self.atr_col_name = None
            logger.warning(f"[{self.__class__.__name__}] on {self.timeframe} could not find a valid ATR instance. Using default period {self.atr_period}.")

        self.long_stop_col = 'CHEX_L'
        self.short_stop_col = 'CHEX_S'
        
    def calculate(self) -> 'ChandelierExitIndicator':
        if not self.atr_col_name or self.atr_col_name not in self.df.columns:
            logger.warning(f"[{self.__class__.__name__}] on {self.timeframe} missing critical ATR data in the main DataFrame. Skipping calculation.")
            self.df[self.long_stop_col] = np.nan
            self.df[self.short_stop_col] = np.nan
            return self

        if len(self.df) < self.atr_period:
            logger.warning(f"Not enough data for Chandelier Exit on {self.timeframe or 'base'}.")
            self.df[self.long_stop_col] = np.nan
            self.df[self.short_stop_col] = np.nan
            return self
        
        atr_values = self.df[self.atr_col_name] * self.atr_multiplier
        
        highest_high = self.df['high'].rolling(window=self.atr_period).max()
        lowest_low = self.df['low'].rolling(window=self.atr_period).min()
        
        self.df[self.long_stop_col] = highest_high - atr_values
        self.df[self.short_stop_col] = lowest_low + atr_values

        return self

    def analyze(self) -> Dict[str, Any]:
        required_cols = [self.long_stop_col, self.short_stop_col, 'close']
        valid_df = self.df.dropna(subset=required_cols)
        
        if valid_df.empty or len(valid_df) < 2:
            logger.warning(f"[{self.__class__.__name__}] on {self.timeframe} has an empty valid_df. Analysis aborted.")
            return {"status": "Insufficient Data"}
        
        last = valid_df.iloc[-1]
        prev = valid_df.iloc[-2]
        
        close_price = last['close']
        long_stop = last[self.long_stop_col]
        short_stop = last[self.short_stop_col]
        
        signal = "Hold"
        message = "Price is between the Chandelier Exit stops."
        
        # Ensure prev is not a single row
        if len(valid_df) > 1:
            if prev['close'] >= prev[self.long_stop_col] and close_price < long_stop:
                signal, message = "Exit Long", f"Price closed below the Long Stop at {round(long_stop, 5)}."
            elif prev['close'] <= prev[self.short_stop_col] and close_price > short_stop:
                signal, message = "Exit Short", f"Price closed above the Short Stop at {round(short_stop, 5)}."
            
        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "values": {
                "close": round(close_price, 5),
                "long_stop": round(long_stop, 5),
                "short_stop": round(short_stop, 5)
            },
            "analysis": {
                "signal": signal,
                "message": message
            }
        }
