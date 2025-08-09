import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

# اطمینان حاصل کنید که این اندیکاتورها از فایل‌های مربوطه و در نسخه‌های نهایی خود وارد شده‌اند
from .base import BaseIndicator
from .atr import AtrIndicator # وابستگی به اندیکاتور ATR کلاس جهانی

logger = logging.getLogger(__name__)

class KeltnerChannelIndicator(BaseIndicator):
    """
    Keltner Channel - Definitive, MTF, and Advanced Analysis World-Class Version
    ----------------------------------------------------------------------------
    This version implements the Keltner Channel with key professional upgrades:
    - EMA is correctly calculated on the Typical Price (HLC/3).
    - Features the standard AiSignalPro MTF architecture.
    - Provides deep analysis, including Breakouts, Channel Touches, and Squeeze detection.
    - Relies on the world-class AtrIndicator for modularity and efficiency.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        # --- Parameters ---
        self.params = kwargs.get('params', {})
        self.ema_period = int(self.params.get('ema_period', 20))
        self.atr_period = int(self.params.get('atr_period', 10))
        self.atr_multiplier = float(self.params.get('atr_multiplier', 2.0))
        self.timeframe = self.params.get('timeframe', None)
        self.squeeze_period = int(self.params.get('squeeze_period', 50)) # Period for squeeze detection

        # --- Dynamic Column Naming ---
        suffix = f'_{self.ema_period}_{self.atr_period}_{self.atr_multiplier}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.upper_col = f'keltner_upper{suffix}'
        self.lower_col = f'keltner_lower{suffix}'
        self.middle_col = f'keltner_middle{suffix}'
        self.bandwidth_col = f'keltner_bw{suffix}'

    def calculate(self) -> 'KeltnerChannelIndicator':
        """Calculates Keltner Channels based on Typical Price, handling MTF internally."""
        base_df = self.df
        
        # ✨ MTF LOGIC: Resample data if a timeframe is specified
        if self.timeframe:
            if not isinstance(base_df.index, pd.DatetimeIndex):
                raise TypeError("DataFrame index must be a DatetimeIndex for MTF.")
            rules = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}
            calc_df = base_df.resample(self.timeframe, label='right', closed='right').apply(rules).dropna()
        else:
            calc_df = base_df.copy()

        if len(calc_df) < max(self.ema_period, self.atr_period):
            logger.warning(f"Not enough data for Keltner Channel on timeframe {self.timeframe or 'base'}.")
            return self

        # --- ✨ Technical Correction: Use Typical Price for EMA ---
        typical_price = (calc_df['high'] + calc_df['low'] + calc_df['close']) / 3
        
        # --- EMA (Middle Band) ---
        middle_band = typical_price.ewm(span=self.ema_period, adjust=False).mean()

        # --- ATR Dependency ---
        atr_params = {'period': self.atr_period, 'timeframe': None}
        atr_indicator = AtrIndicator(calc_df, params=atr_params)
        calc_df_with_atr = atr_indicator.calculate()
        atr_value = calc_df_with_atr[atr_indicator.atr_col] * self.atr_multiplier

        # --- Upper & Lower Bands ---
        upper_band = middle_band + atr_value
        lower_band = middle_band - atr_value
        
        # --- Bandwidth for Squeeze Detection ---
        bandwidth = ((upper_band - lower_band) / middle_band.replace(0, np.nan)) * 100

        # --- Map results back to the original dataframe if MTF ---
        results_df = pd.DataFrame(index=calc_df.index)
        results_df[self.upper_col] = upper_band
        results_df[self.lower_col] = lower_band
        results_df[self.middle_col] = middle_band
        results_df[self.bandwidth_col] = bandwidth

        if self.timeframe:
            final_results = results_df.reindex(base_df.index, method='ffill')
            for col in final_results.columns: self.df[col] = final_results[col]
        else:
            for col in results_df.columns: self.df[col] = results_df[col]
        
        return self

    def analyze(self) -> Dict[str, Any]:
        """Provides deep analysis of price action relative to the Keltner Channel."""
        required_cols = [self.upper_col, self.lower_col, self.middle_col, self.bandwidth_col]
        valid_df = self.df.dropna(subset=required_cols)
        
        if len(valid_df) < self.squeeze_period:
            return {"status": "Insufficient Data", "analysis": {}}

        last = valid_df.iloc[-1]
        close, high, low = last['close'], last['high'], last['low']
        upper, middle, lower = last[self.upper_col], last[self.middle_col], last[self.lower_col]
        
        # --- ✨ Deep Analysis Logic ---
        position, message = "Inside Channel", "Price is contained within the bands."
        if close > upper:
            position, message = "Breakout Above", "Price closed strongly above the upper band."
        elif close < lower:
            position, message = "Breakdown Below", "Price closed strongly below the lower band."
        elif high >= upper:
            position, message = "Touching Upper Band", "Price tested the upper band, potential reversal or breakout."
        elif low <= lower:
            position, message = "Touching Lower Band", "Price tested the lower band, potential reversal or breakdown."
            
        # --- Squeeze Detection ---
        recent_bandwidth = valid_df[self.bandwidth_col].tail(self.squeeze_period)
        is_in_squeeze = last[self.bandwidth_col] <= recent_bandwidth.min()
        
        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "values": {
                "upper_band": round(upper, 5), "middle_band": round(middle, 5), "lower_band": round(lower, 5),
                "bandwidth_percent": round(last[self.bandwidth_col], 2)
            },
            "analysis": {
                "position": position,
                "is_in_squeeze": is_in_squeeze, # True if volatility is at a relative low
                "message": message
            }
        }
