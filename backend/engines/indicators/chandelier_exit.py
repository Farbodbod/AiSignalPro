# backend/engines/indicators/chandelier_exit.py (v6.0 - The Dynamic Engine)
import logging
import pandas as pd
from typing import Dict, Any, Optional

from .base import BaseIndicator
from .utils import get_indicator_config_key

logger = logging.getLogger(__name__)

class ChandelierExitIndicator(BaseIndicator):
    """
    Chandelier Exit - (v6.0 - The Dynamic Engine)
    -----------------------------------------------------------------------------
    This world-class version introduces a dynamic architecture with parameter-based
    column naming, allowing for multiple, conflict-free instances. It is also
    hardened with a limited forward-fill to prevent NaN propagation and features
    a fully standardized, Sentinel-compliant output structure.
    """
    dependencies: list = ['atr']

    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], **kwargs):
        super().__init__(df, params=params, **kwargs)
        self.timeframe = self.params.get('timeframe')
        # ✅ DYNAMIC ARCHITECTURE: Column names are now based on parameters
        self.atr_period = int(self.params.get('dependencies', {}).get('atr', {}).get('period', 22))
        self.atr_multiplier = float(self.params.get('atr_multiplier', 3.0))
        
        suffix = f'_{self.atr_period}_{self.atr_multiplier}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.long_stop_col = f'CHEX_L{suffix}'
        self.short_stop_col = f'CHEX_S{suffix}'

    def calculate(self) -> 'ChandelierExitIndicator':
        my_deps_config = self.params.get("dependencies", {})
        atr_order_params = my_deps_config.get('atr')
        if not atr_order_params:
            logger.error(f"[{self.name}] on {self.timeframe}: 'atr' dependency is not defined.")
            return self
            
        atr_unique_key = get_indicator_config_key('atr', atr_order_params)
        atr_instance = self.dependencies.get(atr_unique_key)
        if not isinstance(atr_instance, BaseIndicator):
            logger.warning(f"[{self.name}] on {self.timeframe}: missing ATR dependency '{atr_unique_key}'.")
            return self

        atr_col_options = [col for col in atr_instance.df.columns if col.startswith('atr_')]
        if not atr_col_options:
            logger.warning(f"[{self.name}] on {self.timeframe}: could not find ATR column in dependency.")
            return self
        atr_col_name = atr_col_options[0]
        
        df_for_calc = self.df.join(atr_instance.df[[atr_col_name]], how='left')
        
        if len(df_for_calc) < self.atr_period:
            logger.warning(f"Not enough data for Chandelier Exit on {self.timeframe or 'base'}.")
            return self
        
        valid_df = df_for_calc.dropna(subset=[atr_col_name, 'high', 'low'])
        atr_values = valid_df[atr_col_name] * self.atr_multiplier
        
        highest_high = valid_df['high'].rolling(window=self.atr_period).max()
        lowest_low = valid_df['low'].rolling(window=self.atr_period).min()
        
        long_stop = highest_high - atr_values
        short_stop = lowest_low + atr_values
        
        # ✅ HARDENED FILL (v6.0): Use a limited forward-fill to prevent NaN propagation.
        fill_limit = 3
        self.df[self.long_stop_col] = long_stop.ffill(limit=fill_limit)
        self.df[self.short_stop_col] = short_stop.ffill(limit=fill_limit)

        return self

    def analyze(self) -> Dict[str, Any]:
        required_cols = [self.long_stop_col, self.short_stop_col]
        empty_analysis = {"values": {}, "analysis": {}}

        if not all(col in self.df.columns for col in required_cols):
            return {"status": "Calculation Incomplete", **empty_analysis}

        valid_df = self.df.dropna(subset=required_cols + ['close'])
        if len(valid_df) < 2: 
            return {"status": "Insufficient Data", **empty_analysis}
        
        last = valid_df.iloc[-1]
        prev = valid_df.iloc[-2]
        
        close_price, long_stop, short_stop = last['close'], last[self.long_stop_col], last[self.short_stop_col]
        
        signal, message = "Hold", "Price is between the Chandelier Exit stops."
        
        if prev['close'] >= prev[self.long_stop_col] and close_price < long_stop:
            signal, message = "Exit Long", f"Price closed below the Long Stop at {round(long_stop, 5)}."
        elif prev['close'] <= prev[self.short_stop_col] and close_price > short_stop:
            signal, message = "Exit Short", f"Price closed above the Short Stop at {round(short_stop, 5)}."
        
        values_content = {"close": round(close_price, 5), "long_stop": round(long_stop, 5), "short_stop": round(short_stop, 5)}
        analysis_content = {"signal": signal, "message": message}

        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "values": values_content,
            "analysis": analysis_content
        }
