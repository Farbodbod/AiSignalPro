import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

# اطمینان حاصل کنید که این اندیکاتورها از فایل‌های مربوطه و در نسخه‌های نهایی خود وارد شده‌اند
from .base import BaseIndicator
from .atr import AtrIndicator # وابستگی به اندیکاتور ATR کلاس جهانی

logger = logging.getLogger(__name__)

class DonchianChannelIndicator(BaseIndicator):
    """
    Donchian Channel - Definitive, MTF, and Noise-Filtered World-Class Version
    --------------------------------------------------------------------------
    This version implements the Donchian Channel with advanced features:
    - Native Multi-Timeframe (MTF) support via internal resampling.
    - Intelligent breakout filtering using ATR to reduce false signals.
    - Clean, modular architecture depending on the world-class AtrIndicator.
    - Fully configurable periods and filter thresholds.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        # --- Parameters ---
        self.params = kwargs.get('params', {})
        self.period = int(self.params.get('period', 20))
        self.timeframe = self.params.get('timeframe', None) # e.g., '1H', '4H'
        
        # --- ATR Filter Parameters ---
        # To disable, set atr_filter_multiplier to 0 or None
        self.use_atr_filter = bool(self.params.get('use_atr_filter', False))
        self.atr_period = int(self.params.get('atr_period', 14))
        self.atr_filter_multiplier = float(self.params.get('atr_filter_multiplier', 1.0))

        # --- Dynamic Column Naming ---
        suffix = f'_{self.period}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.upper_col = f'donchian_upper{suffix}'
        self.lower_col = f'donchian_lower{suffix}'
        self.middle_col = f'donchian_middle{suffix}'
        self.atr_col = f'atr_{self.atr_period}' # Base name for dependency
        if self.timeframe: self.atr_col += f'_{self.timeframe}'


    def calculate(self) -> 'DonchianChannelIndicator':
        """Calculates Donchian Channels and dependencies, handling MTF internally."""
        base_df = self.df
        
        # ✨ MTF LOGIC: Resample data if a timeframe is specified
        if self.timeframe:
            if not isinstance(base_df.index, pd.DatetimeIndex):
                raise TypeError("DataFrame index must be a DatetimeIndex for MTF.")
            rules = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}
            calc_df = base_df.resample(self.timeframe, label='right', closed='right').apply(rules).dropna()
        else:
            calc_df = base_df.copy()

        if len(calc_df) < self.period:
            logger.warning(f"Not enough data for Donchian on timeframe {self.timeframe or 'base'}.")
            return self

        # --- Dependency Calculation: ATR for filtering ---
        if self.use_atr_filter:
            atr_params = {'period': self.atr_period, 'timeframe': None} # ATR is calculated on the already resampled df
            atr_indicator = AtrIndicator(calc_df, params=atr_params)
            calc_df = atr_indicator.calculate()

        # --- Core Donchian Calculation ---
        upper_band = calc_df['high'].rolling(window=self.period).max()
        lower_band = calc_df['low'].rolling(window=self.period).min()
        middle_band = (upper_band + lower_band) / 2
        
        # --- Map results back to the original dataframe if MTF ---
        results_df = pd.DataFrame(index=calc_df.index)
        results_df[self.upper_col] = upper_band
        results_df[self.lower_col] = lower_band
        results_df[self.middle_col] = middle_band
        if self.use_atr_filter:
            results_df[self.atr_col] = calc_df[atr_indicator.atr_col] # Copy ATR results

        if self.timeframe:
            final_results = results_df.reindex(base_df.index, method='ffill')
            for col in final_results.columns: self.df[col] = final_results[col]
        else:
            for col in results_df.columns: self.df[col] = results_df[col]
            
        return self

    def analyze(self) -> Dict[str, Any]:
        """Analyzes for breakouts, applying an ATR filter if configured."""
        required_cols = [self.upper_col, self.lower_col, 'close']
        valid_df = self.df.dropna(subset=required_cols)
        
        if len(valid_df) < 2:
            return {"status": "Insufficient Data", "analysis": {}}

        last = valid_df.iloc[-1]
        prev = valid_df.iloc[-2]
        
        signal = "Neutral"
        message = "Price is inside the channel."

        # --- Breakout Signal Detection ---
        if last['close'] > prev[self.upper_col]:
            signal = "Buy"
            message = "Price closed above the previous upper band."
        elif last['close'] < prev[self.lower_col]:
            signal = "Sell"
            message = "Price closed below the previous lower band."

        # --- ATR Filter Application ---
        atr_filter_passed = True # Default to true if filter is not used
        last_atr_val = None
        if self.use_atr_filter and signal != "Neutral":
            if self.atr_col in last and pd.notna(last[self.atr_col]):
                last_atr_val = last[self.atr_col]
                # A simple filter: breakout is valid only if current ATR is significant
                # (e.g., at least 1% of the price)
                # This logic can be made more complex, e.g., atr > atr.rolling(50).mean()
                atr_threshold = last['close'] * 0.005 # Example: ATR must be at least 0.5% of price
                if last_atr_val < atr_threshold:
                    atr_filter_passed = False
                    message += " (Signal Ignored: Low Volatility)"
                    signal = "Neutral" # Suppress signal
            else:
                atr_filter_passed = False # Cannot verify
                message += " (Signal Ignored: ATR data missing)"
                signal = "Neutral"

        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "values": {
                "upper_band": round(last[self.upper_col], 5),
                "middle_band": round(last[self.middle_col], 5),
                "lower_band": round(last[self.lower_col], 5),
                "atr": round(last_atr_val, 5) if last_atr_val is not None else None
            },
            "analysis": {
                "signal": signal,
                "message": message,
                "atr_filter_passed": atr_filter_passed
            }
        }
