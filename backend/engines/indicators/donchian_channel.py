import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Optional

from .base import BaseIndicator
from .atr import AtrIndicator # FIX: Import AtrIndicator to access the standardized naming method

logger = logging.getLogger(__name__)

class DonchianChannelIndicator(BaseIndicator):
    """
    Donchian Channel - Definitive, World-Class Version (v3.1 - Harmonized Edition)
    ----------------------------------------------------------------------------------
    This version correctly identifies its ATR dependency column using a standardized
    naming convention. The internal resampling logic has been removed to align with
    the IndicatorAnalyzer's single-timeframe calculation architecture.
    """
    dependencies = ['atr']

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.period = int(self.params.get('period', 20))
        self.timeframe = self.params.get('timeframe', None)
        self.use_atr_filter = bool(self.params.get('use_atr_filter', False))
        self.atr_period = int(self.params.get('atr_period', 14))
        
        suffix = f'_{self.period}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.upper_col = f'donchian_upper{suffix}'
        self.lower_col = f'donchian_lower{suffix}'
        self.middle_col = f'donchian_middle{suffix}'

    def calculate(self) -> 'DonchianChannelIndicator':
        """
        ✨ FINAL ARCHITECTURE: No resampling. Just pure calculation.
        """
        df_for_calc = self.df
        
        if len(df_for_calc) < self.period:
            logger.warning(f"Not enough data for Donchian on {self.timeframe or 'base'}.")
            self.df[self.upper_col] = np.nan; self.df[self.lower_col] = np.nan; self.df[self.middle_col] = np.nan
            return self

        # --- Core Donchian Calculation ---
        upper_band = df_for_calc['high'].rolling(window=self.period).max()
        lower_band = df_for_calc['low'].rolling(window=self.period).min()
        middle_band = (upper_band + lower_band) / 2
        
        self.df[self.upper_col] = upper_band
        self.df[self.lower_col] = lower_band
        self.df[self.middle_col] = middle_band
            
        return self

    def analyze(self) -> Dict[str, Any]:
        """
        Analyzes for breakouts, applying an ATR filter if configured and available.
        FIX: Uses the standardized ATR naming method.
        """
        required_cols = [self.upper_col, self.lower_col, 'close']
        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 2:
            return {"status": "Insufficient Data", "analysis": {}}

        last = valid_df.iloc[-1]; prev = valid_df.iloc[-2]
        
        signal, message = "Neutral", "Price is inside the channel."
        if last['close'] > prev[self.upper_col]:
            signal, message = "Buy", "Price closed above the previous upper band."
        elif last['close'] < prev[self.lower_col]:
            signal, message = "Sell", "Price closed below the previous lower band."

        # --- ✨ FINAL ARCHITECTURE: ATR Filter (Consumer Logic) ---
        atr_filter_passed, last_atr_val = True, None
        if self.use_atr_filter and signal != "Neutral":
            # FIX: Use the standardized method to get the ATR column name
            atr_col_name = AtrIndicator._get_atr_col_name(self.atr_period, self.timeframe)
            
            if atr_col_name in last and pd.notna(last[atr_col_name]):
                last_atr_val = last[atr_col_name]
                # A simple volatility threshold: e.g., breakout is only valid if ATR is at least 0.5% of the price
                atr_threshold = last['close'] * 0.005 
                if last_atr_val < atr_threshold:
                    atr_filter_passed, message, signal = False, message + " (Signal Ignored: Low Volatility)", "Neutral"
            else:
                atr_filter_passed, message, signal = False, message + f" (Signal Ignored: ATR column '{atr_col_name}' missing)", "Neutral"
        
        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "values": {
                "upper_band": round(last[self.upper_col], 5),
                "middle_band": round(last[self.middle_col], 5),
                "lower_band": round(last[self.lower_col], 5),
                "atr_for_filter": round(last_atr_val, 5) if last_atr_val is not None else None
            },
            "analysis": {
                "signal": signal,
                "message": message,
                "atr_filter_passed": atr_filter_passed
            }
        }
