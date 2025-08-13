import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Optional

from .base import BaseIndicator
from .atr import AtrIndicator # We need to import this to call its static method

logger = logging.getLogger(__name__)

class KeltnerChannelIndicator(BaseIndicator):
    """
    Keltner Channel - (v5.0 - Multi-Version Aware)
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
        self.ema_period = int(self.params.get('ema_period', 20))
        self.atr_multiplier = float(self.params.get('atr_multiplier', 2.0))
        self.timeframe = self.params.get('timeframe', None)
        self.squeeze_period = int(self.params.get('squeeze_period', 50))
        
        # ✅ MIRACLE UPGRADE: The indicator now reads its specific dependency config.
        # It defaults to a standard ATR(10) which was the original default for this indicator.
        self.atr_dependency_params = self.params.get('dependencies', {}).get('atr', {'period': 10})
        atr_period_for_naming = self.atr_dependency_params.get('period', 10)

        # Column names now correctly reflect the specific ATR period being used
        suffix = f'_{self.ema_period}_{atr_period_for_naming}_{self.atr_multiplier}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.upper_col = f'keltner_upper{suffix}'
        self.lower_col = f'keltner_lower{suffix}'
        self.middle_col = f'keltner_middle{suffix}'
        self.bandwidth_col = f'keltner_bw{suffix}'

    def calculate(self) -> 'KeltnerChannelIndicator':
        """ Calculates Keltner Channels using its required, specific version of ATR. """
        df_for_calc = self.df
        
        atr_period = self.atr_dependency_params.get('period', 10)
        if len(df_for_calc) < max(self.ema_period, atr_period):
            logger.warning(f"Not enough data for Keltner Channel on {self.timeframe or 'base'}.")
            for col in [self.upper_col, self.lower_col, self.middle_col, self.bandwidth_col]:
                self.df[col] = np.nan
            return self

        # ✅ MIRACLE UPGRADE: Generates the required column name using the new universal language.
        atr_col_name = AtrIndicator.get_col_name(self.atr_dependency_params, self.timeframe)
        
        if atr_col_name not in df_for_calc.columns:
            raise ValueError(f"Required ATR column '{atr_col_name}' not found for Keltner Channel. Ensure ATR dependency is correctly configured.")
        
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
        """ Provides deep analysis of price action relative to the Keltner Channel. """
        required_cols = [self.upper_col, self.lower_col, self.middle_col, self.bandwidth_col]
        valid_df = self.df.dropna(subset=required_cols)
        
        if len(valid_df) < self.squeeze_period:
            return {"status": "Insufficient Data"}

        last = valid_df.iloc[-1]
        close = last['close']
        upper, middle, lower = last[self.upper_col], last[self.middle_col], last[self.lower_col]
        
        position = "Inside Channel"
        if close > upper: position = "Breakout Above"
        elif close < lower: position = "Breakdown Below"
            
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
                "is_in_squeeze": is_in_squeeze
            }
        }
