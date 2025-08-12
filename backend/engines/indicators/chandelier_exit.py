import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Optional

from .base import BaseIndicator
from .atr import AtrIndicator # We need to import this to call its static method

logger = logging.getLogger(__name__)

class ChandelierExitIndicator(BaseIndicator):
    """
    Chandelier Exit - (v4.0 - Multi-Version Aware)
    -----------------------------------------------------------------------------
    This world-class version is fully compatible with the IndicatorAnalyzer v9.0's
    Multi-Version Engine. It intelligently reads its dependency configuration
    to request the specific version of ATR it needs, ensuring a robust and
    error-free calculation process.
    """
    # ✅ MIRACLE UPGRADE: Dependency is now declared in config, not hardcoded here.
    dependencies: list = []

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.atr_multiplier = float(self.params.get('atr_multiplier', 3.0))
        self.timeframe = self.params.get('timeframe', None)

        # ✅ MIRACLE UPGRADE: The indicator now reads its specific dependency config.
        # It defaults to a standard ATR(22) which was its original default.
        self.atr_dependency_params = self.params.get('dependencies', {}).get('atr', {'period': 22})
        atr_period_for_naming = self.atr_dependency_params.get('period', 22)

        # Column names now correctly reflect the specific ATR period being used
        suffix = f'_{atr_period_for_naming}_{self.atr_multiplier}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.long_stop_col = f'ch_long_stop{suffix}' # Shortened for clarity
        self.short_stop_col = f'ch_short_stop{suffix}'
        
    def calculate(self) -> 'ChandelierExitIndicator':
        """ Calculates the Chandelier Exit lines using its required, specific version of ATR. """
        df_for_calc = self.df
        atr_period = self.atr_dependency_params.get('period', 22)

        if len(df_for_calc) < atr_period:
            logger.warning(f"Not enough data for Chandelier Exit on {self.timeframe or 'base'}.")
            self.df[self.long_stop_col] = np.nan
            self.df[self.short_stop_col] = np.nan
            return self

        # ✅ MIRACLE UPGRADE: Generates the required column name dynamically
        # based on its dependency's parameters, using the dependency's own static method.
        atr_col_name = AtrIndicator.get_col_name(self.atr_dependency_params, self.timeframe)
        
        if atr_col_name not in df_for_calc.columns:
            raise ValueError(f"Required ATR column '{atr_col_name}' not found. Ensure ATR dependency is correctly configured.")

        atr_values = df_for_calc[atr_col_name] * self.atr_multiplier
        
        highest_high = df_for_calc['high'].rolling(window=atr_period).max()
        lowest_low = df_for_calc['low'].rolling(window=atr_period).min()
        
        self.df[self.long_stop_col] = highest_high - atr_values
        self.df[self.short_stop_col] = lowest_low + atr_values

        return self

    def analyze(self) -> Dict[str, Any]:
        """ Provides a bias-free analysis of the price relative to the exit lines. """
        required_cols = [self.long_stop_col, self.short_stop_col, 'close']
        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 2: return {"status": "Insufficient Data"}
        
        last = valid_df.iloc[-1]
        prev = valid_df.iloc[-2]
        
        close_price = last['close']
        long_stop = last[self.long_stop_col]
        short_stop = last[self.short_stop_col]
        
        signal = "Hold"
        message = "Price is between the Chandelier Exit stops."
        
        # A true exit signal occurs on the close of the candle that crosses the line
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
