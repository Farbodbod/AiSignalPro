# backend/engines/indicators/chandelier_exit.py
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class ChandelierExitIndicator(BaseIndicator):
    """
    Chandelier Exit - (v5.0 - Dependency Injection Native)
    -----------------------------------------------------------------------------
    This version is rewritten to natively support the Dependency Injection (DI)
    architecture. It no longer relies on static methods or predicting column names.
    Instead, it directly consumes the ATR instance passed to it by the modern
    IndicatorAnalyzer, ensuring a robust, decoupled, and error-free calculation process.
    """
    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], dependencies: Dict[str, BaseIndicator], **kwargs):
        super().__init__(df, params=params, dependencies=dependencies, **kwargs)
        self.atr_multiplier = float(self.params.get('atr_multiplier', 3.0))
        self.timeframe = self.params.get('timeframe')
        self.atr_period = int(self.dependencies.get('atr').params.get('period', 22))

        # Column names are simplified. The DI architecture makes complex names obsolete.
        self.long_stop_col = 'CHEX_L'
        self.short_stop_col = 'CHEX_S'
        
    def calculate(self) -> 'ChandelierExitIndicator':
        """ 
        Calculates the Chandelier Exit lines by directly consuming its ATR dependency.
        """
        # 1. Directly receive the ATR instance injected by the Analyzer.
        atr_instance = self.dependencies.get('atr')
        if not atr_instance:
            logger.warning(f"[{self.__class__.__name__}] on {self.timeframe} missing critical ATR dependency. Skipping calculation.")
            return self

        # 2. Intelligently find the required ATR column from the dependency's DataFrame.
        atr_df = atr_instance.df
        atr_col_options = [col for col in atr_df.columns if 'ATR' in col.upper()]
        if not atr_col_options:
            logger.warning(f"[{self.__class__.__name__}] on {self.timeframe} could not find ATR column in dependency dataframe.")
            return self
        atr_col_name = atr_col_options[0]

        # 3. Join the necessary ATR data into this indicator's main DataFrame.
        self.df = self.df.join(atr_df[[atr_col_name]], how='left')

        # 4. Perform the core Chandelier Exit calculation (Logic is 100% preserved).
        if len(self.df) < self.atr_period:
            logger.warning(f"Not enough data for Chandelier Exit on {self.timeframe or 'base'}.")
            self.df[self.long_stop_col] = np.nan
            self.df[self.short_stop_col] = np.nan
            return self
        
        atr_values = self.df[atr_col_name] * self.atr_multiplier
        
        highest_high = self.df['high'].rolling(window=self.atr_period).max()
        lowest_low = self.df['low'].rolling(window=self.atr_period).min()
        
        self.df[self.long_stop_col] = highest_high - atr_values
        self.df[self.short_stop_col] = lowest_low + atr_values

        return self

    def analyze(self) -> Dict[str, Any]:
        """ 
        Provides a bias-free analysis of the price relative to the exit lines.
        This entire method's logic is preserved 100% from the previous version.
        """
        required_cols = [self.long_stop_col, self.short_stop_col, 'close']
        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 2: 
            return {"status": "Insufficient Data"}
        
        last = valid_df.iloc[-1]
        prev = valid_df.iloc[-2]
        
        close_price = last['close']
        long_stop = last[self.long_stop_col]
        short_stop = last[self.short_stop_col]
        
        signal = "Hold"
        message = "Price is between the Chandelier Exit stops."
        
        # The signal generation logic is identical to the previous version, ensuring consistency.
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
