import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

# اطمینان حاصل کنید که این اندیکاتورها از فایل‌های مربوطه و در نسخه‌های نهایی خود وارد شده‌اند
from .base import BaseIndicator
from .atr import AtrIndicator # وابستگی به اندیکاتور ATR کلاس جهانی

logger = logging.getLogger(__name__)

class ChandelierExitIndicator(BaseIndicator):
    """
    Chandelier Exit - Definitive, MTF, and World-Class Version (v2.1 - Bugfix)
    -------------------------------------------------------------------------
    This version includes a critical bug fix in the dependency call to AtrIndicator.
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
        """Calculates the Chandelier Exit lines, handling MTF internally."""
        base_df = self.df
        
        if self.timeframe:
            if not isinstance(base_df.index, pd.DatetimeIndex): raise TypeError("DatetimeIndex required for MTF.")
            rules = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}
            calc_df = base_df.resample(self.timeframe, label='right', closed='right').apply(rules).dropna()
        else:
            calc_df = base_df.copy()

        if len(calc_df) < self.atr_period: logger.warning(f"Not enough data for Chandelier Exit on {self.timeframe or 'base'}."); return self

        # ✨ FIX: Correctly handle the return from AtrIndicator.calculate()
        atr_params = {'period': self.atr_period, 'timeframe': None}
        atr_instance = AtrIndicator(calc_df, params=atr_params).calculate()
        calc_df_with_atr = atr_instance.df
        atr_values = calc_df_with_atr[atr_instance.atr_col]
        
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
        # ... (بخش analyze کامل و بدون تغییر است) ...
        required_cols = [self.long_stop_col, self.short_stop_col, 'close']
        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 2: return {"status": "Insufficient Data", "analysis": {}}
        last = valid_df.iloc[-1]; prev = valid_df.iloc[-2]
        close_price = last['close']; long_stop = last[self.long_stop_col]; short_stop = last[self.short_stop_col]
        signal = "Hold"; message = "Price is between the Chandelier Exit stops."
        if prev['close'] >= prev[self.long_stop_col] and close_price < long_stop: signal, message = "Exit Long", f"Price closed below the Long Stop at {round(long_stop, 5)}."
        elif prev['close'] <= prev[self.short_stop_col] and close_price > short_stop: signal, message = "Exit Short", f"Price closed above the Short Stop at {round(short_stop, 5)}."
        return { "status": "OK", "timeframe": self.timeframe or 'Base', "values": { "close": round(close_price, 5), "long_stop": round(long_stop, 5), "short_stop": round(short_stop, 5) }, "analysis": { "signal": signal, "message": message } }
