import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class KeltnerChannelIndicator(BaseIndicator):
    """
    Keltner Channel - Definitive, World-Class Version (v4.0 - Final Architecture)
    -----------------------------------------------------------------------------
    This version adheres to the final AiSignalPro architecture. It performs its
    calculations on the pre-resampled dataframe provided by the IndicatorAnalyzer,
    making it a pure, efficient, and powerful engine for analyzing volatility
    channels and squeezes.
    """
    dependencies = ['atr']

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.ema_period = int(self.params.get('ema_period', 20))
        self.atr_period = int(self.params.get('atr_period', 10))
        self.atr_multiplier = float(self.params.get('atr_multiplier', 2.0))
        self.timeframe = self.params.get('timeframe', None)
        self.squeeze_period = int(self.params.get('squeeze_period', 50))

        suffix = f'_{self.ema_period}_{self.atr_period}_{self.atr_multiplier}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.upper_col = f'keltner_upper{suffix}'
        self.lower_col = f'keltner_lower{suffix}'
        self.middle_col = f'keltner_middle{suffix}'
        self.bandwidth_col = f'keltner_bw{suffix}'

    def calculate(self) -> 'KeltnerChannelIndicator':
        """
        ✨ FINAL ARCHITECTURE: No resampling. Just pure calculation.
        The dataframe received is already at the correct timeframe.
        """
        df_for_calc = self.df
        
        if len(df_for_calc) < max(self.ema_period, self.atr_period):
            logger.warning(f"Not enough data for Keltner Channel on {self.timeframe or 'base'}.")
            for col in [self.upper_col, self.lower_col, self.middle_col, self.bandwidth_col]:
                self.df[col] = np.nan
            return self

        atr_col_name = f'atr_{self.atr_period}'
        if self.timeframe: atr_col_name += f'_{self.timeframe}'
        
        if atr_col_name not in df_for_calc.columns:
            raise ValueError(f"Required ATR column '{atr_col_name}' not found. Ensure ATR is calculated first by the Analyzer.")
        
        typical_price = (df_for_calc['high'] + df_for_calc['low'] + df_for_calc['close']) / 3
        middle_band = typical_price.ewm(span=self.ema_period, adjust=False).mean()
        atr_value = df_for_calc[atr_col_name] * self.atr_multiplier
        
        upper_band = middle_band + atr_value
        lower_band = middle_band - atr_value
        bandwidth = ((upper_band - lower_band) / middle_band.replace(0, np.nan)) * 100

        self.df[self.upper_col] = upper_band
        self.df[self.lower_col] = lower_band
        self.df[self.middle_col] = middle_band
        self.df[self.bandwidth_col] = bandwidth
        
        return self

    def analyze(self) -> Dict[str, Any]:
        """
        Provides deep analysis of price action relative to the Keltner Channel.
        This powerful analysis logic remains unchanged.
        """
        required_cols = [self.upper_col, self.lower_col, self.middle_col, self.bandwidth_col]
        valid_df = self.df.dropna(subset=required_cols)
        
        if len(valid_df) < self.squeeze_period:
            return {"status": "Insufficient Data", "analysis": {}}

        last = valid_df.iloc[-1]
        close, high, low = last['close'], last['high'], last['low']
        upper, middle, lower = last[self.upper_col], last[self.middle_col], last[self.lower_col]
        
        position, message = "Inside Channel", "Price is contained within the bands."
        if close > upper:
            position, message = "Breakout Above", "Price closed strongly above the upper band."
        elif close < lower:
            position, message = "Breakdown Below", "Price closed strongly below the lower band."
        elif high >= upper:
            position, message = "Touching Upper Band", "Price tested the upper band."
        elif low <= lower:
            position, message = "Touching Lower Band", "Price tested the lower band."
            
        recent_bandwidth = valid_df[self.bandwidth_col].tail(self.squeeze_period)
        is_in_squeeze = last[self.bandwidth_col] <= recent_bandwidth.min()
        
        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "values": {
                "upper_band": round(upper, 5),
                "middle_band": round(middle, 5),
                "lower_band": round(lower, 5),
                "bandwidth_percent": round(last[self.bandwidth_col], 2)
            },
            "analysis": {
                "position": position,
                "is_in_squeeze": is_in_squeeze,
                "message": message
            }
        }
