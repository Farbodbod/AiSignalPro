import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

from .base import BaseIndicator
# ✨ REFINEMENT: The indicator itself no longer needs to import its dependencies.

logger = logging.getLogger(__name__)

class ChandelierExitIndicator(BaseIndicator):
    """
    Chandelier Exit - Definitive, MTF & World-Class Version (v3.0 - No Internal Deps)
    ----------------------------------------------------------------------------------
    This version adheres to the final AiSignalPro architecture. It does not
    calculate its own dependencies. Instead, it relies on the IndicatorAnalyzer
    to provide the necessary ATR column, making it a pure, efficient, and
    robust calculation engine.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        # --- Parameters ---
        self.params = kwargs.get('params', {})
        self.atr_period = int(self.params.get('atr_period', 22))
        self.atr_multiplier = float(self.params.get('atr_multiplier', 3.0))
        self.timeframe = self.params.get('timeframe', None)

        # --- Dynamic Column Naming ---
        suffix = f'_{self.atr_period}_{self.atr_multiplier}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.long_stop_col = f'chandelier_long_stop{suffix}'
        self.short_stop_col = f'chandelier_short_stop{suffix}'
        
    def calculate(self) -> 'ChandelierExitIndicator':
        """
        Calculates the Chandelier Exit lines, assuming the ATR column is already present.
        """
        base_df = self.df
        
        if self.timeframe:
            if not isinstance(base_df.index, pd.DatetimeIndex): raise TypeError("DatetimeIndex required for MTF.")
            rules = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}
            calc_df = base_df.resample(self.timeframe, label='right', closed='right').apply(rules).dropna()
        else:
            calc_df = base_df.copy()

        if len(calc_df) < self.atr_period:
            logger.warning(f"Not enough data for Chandelier Exit on {self.timeframe or 'base'}.")
            # Ensure columns exist even if we can't calculate, to prevent KeyErrors later
            self.df[self.long_stop_col] = np.nan
            self.df[self.short_stop_col] = np.nan
            return self

        # ✨ THE MIRACLE FIX: No internal dependency calls.
        # It now expects the ATR column to have been pre-calculated by the Analyzer.
        atr_col_name = f'atr_{self.atr_period}'
        if self.timeframe: atr_col_name += f'_{self.timeframe}'
        
        if atr_col_name not in calc_df.columns:
            raise ValueError(f"Required ATR column '{atr_col_name}' not found for Chandelier Exit calculation. Ensure ATR is calculated first by the Analyzer.")

        atr_values = calc_df[atr_col_name]
        
        # --- Core Chandelier Calculation ---
        highest_high = calc_df['high'].rolling(window=self.atr_period).max()
        lowest_low = calc_df['low'].rolling(window=self.atr_period).min()
        
        long_stop = highest_high - (atr_values * self.atr_multiplier)
        short_stop = lowest_low + (atr_values * self.atr_multiplier)
        
        # --- Map results back to the original dataframe if MTF ---
        results_df = pd.DataFrame(index=calc_df.index)
        results_df[self.long_stop_col] = long_stop
        results_df[self.short_stop_col] = short_stop
        
        if self.timeframe:
            final_results = results_df.reindex(base_df.index, method='ffill')
            self.df[self.long_stop_col] = final_results[self.long_stop_col]
            self.df[self.short_stop_col] = final_results[self.short_stop_col]
        else:
            self.df[self.long_stop_col] = results_df[self.long_stop_col]
            self.df[self.short_stop_col] = results_df[self.short_stop_col]

        return self

    def analyze(self) -> Dict[str, Any]:
        """ Provides a bias-free analysis of the price relative to the exit lines. """
        required_cols = [self.long_stop_col, self.short_stop_col, 'close']
        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 2: return {"status": "Insufficient Data", "analysis": {}}
        
        last = valid_df.iloc[-1]
        prev = valid_df.iloc[-2]
        
        close_price = last['close']
        long_stop = last[self.long_stop_col]
        short_stop = last[self.short_stop_col]
        
        signal = "Hold"
        message = "Price is between the Chandelier Exit stops."
        
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
