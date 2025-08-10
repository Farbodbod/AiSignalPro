import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class ChandelierExitIndicator(BaseIndicator):
    """
    Chandelier Exit - Definitive, World-Class Version (v3.1 - Final Architecture)
    -----------------------------------------------------------------------------
    This version adheres to the final AiSignalPro architecture. It performs its
    calculations on the pre-resampled dataframe provided by the IndicatorAnalyzer,
    making it a pure, efficient, and powerful trailing stop engine.
    """
    dependencies = ['atr']

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.atr_period = int(self.params.get('atr_period', 22))
        self.atr_multiplier = float(self.params.get('atr_multiplier', 3.0))
        self.timeframe = self.params.get('timeframe', None)

        suffix = f'_{self.atr_period}_{self.atr_multiplier}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.long_stop_col = f'chandelier_long_stop{suffix}'
        self.short_stop_col = f'chandelier_short_stop{suffix}'
        
    def calculate(self) -> 'ChandelierExitIndicator':
        """
        ✨ FINAL ARCHITECTURE: No resampling. Just pure calculation.
        Calculates the Chandelier Exit lines, assuming the ATR column is already present.
        """
        df_for_calc = self.df
        
        if len(df_for_calc) < self.atr_period:
            logger.warning(f"Not enough data for Chandelier Exit on {self.timeframe or 'base'}.")
            self.df[self.long_stop_col] = np.nan
            self.df[self.short_stop_col] = np.nan
            return self

        atr_col_name = f'atr_{self.atr_period}'
        if self.timeframe: atr_col_name += f'_{self.timeframe}'
        
        if atr_col_name not in df_for_calc.columns:
            raise ValueError(f"Required ATR column '{atr_col_name}' not found. Ensure ATR is calculated first by the Analyzer.")

        atr_values = df_for_calc[atr_col_name] * self.atr_multiplier
        
        highest_high = df_for_calc['high'].rolling(window=self.atr_period).max()
        lowest_low = df_for_calc['low'].rolling(window=self.atr_period).min()
        
        self.df[self.long_stop_col] = highest_high - atr_values
        self.df[self.short_stop_col] = lowest_low + atr_values

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
