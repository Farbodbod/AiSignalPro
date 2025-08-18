# backend/engines/indicators/chandelier_exit.py (v5.2 - Final & Inherited Init)
import logging
import pandas as pd
from typing import Dict, Any, Optional

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class ChandelierExitIndicator(BaseIndicator):
    """
    Chandelier Exit - (v5.2 - Final & Inherited Init)
    -----------------------------------------------------------------------------
    This definitive version is re-engineered to natively support the Dependency
    Injection (DI) architecture. It robustly consumes the ATR instance, eliminating
    fragile dependencies while ensuring the core calculation and analysis logic
    remain 100% intact. The unnecessary __init__ is removed for cleaner code.
    """
    strategy_name: "ChandelierExitIndicator"

    default_config = {
        "atr_multiplier": 3.0
    }
    
    # NOTE: No __init__ method is needed. This class now correctly inherits the
    # powerful constructor from BaseIndicator, making the code cleaner.
    
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
        
        atr_period = int(atr_instance.params.get('period', 22))
        atr_multiplier = float(self.config.get('atr_multiplier', 3.0))

        # 4. Perform the core Chandelier Exit calculation (Logic is 100% preserved).
        if len(self.df) < atr_period:
            logger.warning(f"Not enough data for Chandelier Exit on {self.timeframe or 'base'}.")
            self.df['CHEX_L'] = pd.NA
            self.df['CHEX_S'] = pd.NA
            return self
        
        atr_values = self.df[atr_col_name] * atr_multiplier
        
        highest_high = self.df['high'].rolling(window=atr_period).max()
        lowest_low = self.df['low'].rolling(window=atr_period).min()
        
        self.df['CHEX_L'] = highest_high - atr_values
        self.df['CHEX_S'] = lowest_low + atr_values

        return self

    def analyze(self) -> Dict[str, Any]:
        """ 
        Provides a bias-free analysis of the price relative to the exit lines.
        This entire method's logic is preserved 100% from the previous version.
        """
        required_cols = ['CHEX_L', 'CHEX_S', 'close']
        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 2: 
            return {"status": "Insufficient Data"}
        
        last = valid_df.iloc[-1]
        prev = valid_df.iloc[-2]
        
        close_price = last['close']
        long_stop = last['CHEX_L']
        short_stop = last['CHEX_S']
        
        signal = "Hold"
        message = "Price is between the Chandelier Exit stops."
        
        if prev['close'] >= prev['CHEX_L'] and close_price < long_stop:
            signal, message = "Exit Long", f"Price closed below the Long Stop at {round(long_stop, 5)}."
        elif prev['close'] <= prev['CHEX_S'] and close_price > short_stop:
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
