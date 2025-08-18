# backend/engines/indicators/chandelier_exit.py
import logging
import pandas as pd
import json
from typing import Dict, Any, Optional

from .base import BaseIndicator
from .utils import get_indicator_config_key # ✅ World-Class Practice: Import from shared utils

logger = logging.getLogger(__name__)

class ChandelierExitIndicator(BaseIndicator):
    """
    Chandelier Exit - (v5.5 - Unified Utils)
    -----------------------------------------------------------------------------
    This definitive version is fully DI-native and hardened. It no longer contains
    a local copy of the helper functions, instead importing them from the shared
    `utils.py` module, adhering to the DRY principle and professional software
    engineering standards. All logic is 100% preserved.
    """
    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], dependencies: Dict[str, BaseIndicator], **kwargs):
        super().__init__(df, params=params, dependencies=dependencies, **kwargs)
        self.timeframe = self.params.get('timeframe')

    def calculate(self) -> 'ChandelierExitIndicator':
        """ 
        Calculates the Chandelier Exit lines by correctly looking up its ATR dependency.
        """
        # 1. Get this indicator's own dependency configuration from its parameters.
        my_deps_config = self.params.get("dependencies", {})
        atr_order_params = my_deps_config.get('atr')

        if not atr_order_params:
            logger.error(f"[{self.__class__.__name__}] on {self.timeframe} cannot run because 'atr' dependency is not defined in its config.")
            return self
            
        # 2. Reconstruct the full, unique key for the required dependency.
        atr_unique_key = get_indicator_config_key('atr', atr_order_params)
        
        # 3. Get the dependency instance using the correct, full unique key.
        atr_instance = self.dependencies.get(atr_unique_key)
        
        if not isinstance(atr_instance, BaseIndicator):
            logger.warning(f"[{self.__class__.__name__}] on {self.timeframe} missing critical ATR dependency instance ('{atr_unique_key}'). Skipping calculation.")
            return self

        atr_df = atr_instance.df
        atr_col_options = [col for col in atr_df.columns if 'ATR' in col.upper()]
        if not atr_col_options:
            logger.warning(f"[{self.__class__.__name__}] on {self.timeframe} could not find ATR column in dependency dataframe.")
            return self
        atr_col_name = atr_col_options[0]
        
        self.df = self.df.join(atr_df[[atr_col_name]], how='left')
        
        atr_period = int(atr_instance.params.get('period', 22))
        atr_multiplier = float(self.config.get('atr_multiplier', 3.0))

        if len(self.df) < atr_period:
            return self
        
        atr_values = self.df[atr_col_name].dropna() * atr_multiplier
        
        highest_high = self.df['high'].rolling(window=atr_period).max()
        lowest_low = self.df['low'].rolling(window=atr_period).min()
        
        self.df['CHEX_L'] = highest_high - atr_values
        self.df['CHEX_S'] = lowest_low + atr_values

        return self

    def analyze(self) -> Dict[str, Any]:
        """ 
        The analysis logic is now protected by a guard clause.
        """
        required_cols = ['CHEX_L', 'CHEX_S']
        if not all(col in self.df.columns for col in required_cols):
            return {"status": "Calculation Incomplete - Required columns missing"}

        valid_df = self.df.dropna(subset=required_cols + ['close'])
        if len(valid_df) < 2: 
            return {"status": "Insufficient Data"}
        
        last, prev = valid_df.iloc[-1], valid_df.iloc[-2]
        close_price, long_stop, short_stop = last['close'], last['CHEX_L'], last['CHEX_S']
        
        signal, message = "Hold", "Price is between the Chandelier Exit stops."
        
        if prev['close'] >= prev['CHEX_L'] and close_price < long_stop:
            signal, message = "Exit Long", f"Price closed below the Long Stop at {round(long_stop, 5)}."
        elif prev['close'] <= prev['CHEX_S'] and close_price > short_stop:
            signal, message = "Exit Short", f"Price closed above the Short Stop at {round(short_stop, 5)}."
            
        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "values": {"close": round(close_price, 5), "long_stop": round(long_stop, 5), "short_stop": round(short_stop, 5)},
            "analysis": {"signal": signal, "message": message}
        }
