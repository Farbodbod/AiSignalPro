import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class VwapBandsIndicator(BaseIndicator):
    """
    VWAP Bands - Definitive, World-Class Version (v4.2 - Final & Harmonized)
    ----------------------------------------------------------------
    This advanced version of VWAP provides a flexible, period-based reset
    mechanism and enriches the analysis with statistical metrics like Z-score
    and Bandwidth. The analyze() method is hardened to be fully bias-free.
    """
    dependencies: list = []
    ALLOWED_METHODS = {'standard', 'fibonacci', 'camarilla'}

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.reset_period = str(self.params.get('reset_period', 'D'))
        self.std_dev_multiplier = float(self.params.get('std_dev_multiplier', 2.0))
        self.precision = int(self.params.get('precision', 5))
        
        # ✨ اصلاح اصلی: اضافه کردن مقداردهی اولیه برای timeframe برای حل خطای AttributeError
        self.timeframe = self.params.get('timeframe', None)

        # Suffix uses a simplified name for reset_period for cleaner columns
        tf_name = self.timeframe if self.timeframe else self.reset_period
        suffix = f'_{tf_name}_{self.std_dev_multiplier}'
        self.vwap_col = f'vwap{suffix}'
        self.upper_col = f'vwap_upper{suffix}'
        self.lower_col = f'vwap_lower{suffix}'
        self.zscore_col = f'vwap_zscore{suffix}'
        self.bandwidth_col = f'vwap_bw{suffix}'

    def calculate(self) -> 'VwapBandsIndicator':
        """
        ✨ FINAL ARCHITECTURE: This indicator's logic is fundamentally different
        and does not use the standard MTF resampling. It uses groupby for period
        resets, which is the correct approach for VWAP. This method is already
        in its final, correct state.
        """
        if not isinstance(self.df.index, pd.DatetimeIndex):
            raise TypeError("DataFrame index must be a DatetimeIndex for VWAP calculation.")
            
        # The received df is already at the correct timeframe from the Analyzer
        df_for_calc = self.df
        
        tp = (df_for_calc['high'] + df_for_calc['low'] + df_for_calc['close']) / 3.0
        tp_volume = tp * df_for_calc['volume']

        grouper = pd.Grouper(freq=self.reset_period)
        
        cumulative_volume = df_for_calc['volume'].groupby(grouper).cumsum()
        cumulative_tp_volume = tp_volume.groupby(grouper).cumsum()
        vwap = cumulative_tp_volume / cumulative_volume.replace(0, np.nan)
        
        squared_diff = ((tp - vwap)**2) * df_for_calc['volume']
        cumulative_squared_diff = squared_diff.groupby(grouper).cumsum()
        daily_variance = cumulative_squared_diff / cumulative_volume.replace(0, np.nan)
        daily_std_dev = np.sqrt(daily_variance)

        self.df[self.vwap_col] = vwap
        self.df[self.upper_col] = vwap + (daily_std_dev * self.std_dev_multiplier)
        self.df[self.lower_col] = vwap - (daily_std_dev * self.std_dev_multiplier)
        self.df[self.bandwidth_col] = ((self.df[self.upper_col] - self.df[self.lower_col]) / vwap.replace(0, np.nan)) * 100
        self.df[self.zscore_col] = (df_for_calc['close'] - vwap) / daily_std_dev.replace(0, np.nan)

        return self

    def analyze(self) -> Dict[str, Any]:
        """
        Analyzes the price's deviation from VWAP for mean-reversion signals
        using the last *closed* candle to be 100% bias-free.
        """
        required_cols = [self.vwap_col, self.upper_col, self.lower_col, self.zscore_col]
        
        # ✨ BIAS-FREE FIX: Ensure we have at least two rows to safely access iloc[-2]
        if len(self.df.dropna(subset=required_cols)) < 2:
            return {"status": "Insufficient Data"}

        # Use the last *closed* candle for all analysis
        last_closed_candle = self.df.iloc[-2]
        
        if pd.isna(last_closed_candle[required_cols]).any():
            return {"status": "Insufficient Data for last closed candle"}
            
        close_price = last_closed_candle['close']
        vwap = last_closed_candle[self.vwap_col]
        upper = last_closed_candle[self.upper_col]
        lower = last_closed_candle[self.lower_col]
        z_score = last_closed_candle[self.zscore_col]

        position = "Inside Bands"
        signal = "Hold"
        message = "Price is within the VWAP standard deviation bands."
        
        if close_price > upper:
            position = "Overextended Above"
            signal = "Sell"
            message = f"Price is overextended above the upper band (Z-score: {round(z_score, 2)})."
        elif close_price < lower:
            position = "Overextended Below"
            signal = "Buy"
            message = f"Price is overextended below the lower band (Z-score: {round(z_score, 2)})."

        return {
            "status": "OK",
            "reset_period": self.reset_period,
            "values": {
                "vwap": round(vwap, 5),
                "upper_band": round(upper, 5),
                "lower_band": round(lower, 5),
                "bandwidth_percent": round(last_closed_candle.get(self.bandwidth_col, 0), 2),
                "z_score": round(z_score, 2)
            },
            "analysis": {
                "position": position,
                "signal": signal,
                "message": message
            }
        }
