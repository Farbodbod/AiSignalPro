import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

# اطمینان حاصل کنید که این اندیکاتور از فایل مربوطه وارد شده‌ است
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class VwapBandsIndicator(BaseIndicator):
    """
    VWAP Bands - Definitive, Statistical, and Flexible-Reset World-Class Version
    -----------------------------------------------------------------------------
    This advanced version of VWAP provides a flexible, period-based reset mechanism
    (e.g., Daily, Weekly, 4-Hour) and enriches the analysis with statistical
    metrics like Z-score and Bandwidth, making it a powerful mean-reversion tool.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        # --- Parameters ---
        self.params = kwargs.get('params', {})
        # The reset period frequency (e.g., 'D' for Daily, 'W' for Weekly, '4H')
        self.reset_period = str(self.params.get('reset_period', 'D'))
        self.std_dev_multiplier = float(self.params.get('std_dev_multiplier', 2.0))
        
        # --- Dynamic Column Naming ---
        suffix = f'_{self.reset_period}_{self.std_dev_multiplier}'
        self.vwap_col = f'vwap{suffix}'
        self.upper_col = f'vwap_upper{suffix}'
        self.lower_col = f'vwap_lower{suffix}'
        self.zscore_col = f'vwap_zscore{suffix}'
        self.bandwidth_col = f'vwap_bw{suffix}'

    def calculate(self) -> 'VwapBandsIndicator':
        """Calculates VWAP and its bands, resetting based on the specified reset_period."""
        if not isinstance(self.df.index, pd.DatetimeIndex):
            raise TypeError("DataFrame index must be a DatetimeIndex for VWAP calculation.")
            
        df = self.df.copy()
        
        # --- Core VWAP Calculation ---
        tp = (df['high'] + df['low'] + df['close']) / 3.0
        tp_volume = tp * df['volume']

        # ✨ Flexible Reset Logic using pd.Grouper
        grouper = pd.Grouper(freq=self.reset_period)
        
        cumulative_volume = df['volume'].groupby(grouper).cumsum()
        cumulative_tp_volume = tp_volume.groupby(grouper).cumsum()

        # Safe division: where cumulative_volume is 0, vwap is NaN
        vwap = cumulative_tp_volume / cumulative_volume.replace(0, np.nan)
        
        # --- Weighted Variance & Standard Deviation Bands ---
        squared_diff = ((tp - vwap)**2) * df['volume']
        cumulative_squared_diff = squared_diff.groupby(grouper).cumsum()
        
        # Safe division for variance
        daily_variance = cumulative_squared_diff / cumulative_volume.replace(0, np.nan)
        daily_std_dev = np.sqrt(daily_variance)

        self.df[self.vwap_col] = vwap
        self.df[self.upper_col] = vwap + (daily_std_dev * self.std_dev_multiplier)
        self.df[self.lower_col] = vwap - (daily_std_dev * self.std_dev_multiplier)
        
        # --- ✨ Advanced Statistical Metrics ---
        # Bandwidth Percentage
        self.df[self.bandwidth_col] = ((self.df[self.upper_col] - self.df[self.lower_col]) / vwap.replace(0, np.nan)) * 100
        # Z-Score (how many standard deviations the close is from the VWAP)
        self.df[self.zscore_col] = (df['close'] - vwap) / daily_std_dev.replace(0, np.nan)

        return self

    def analyze(self) -> Dict[str, Any]:
        """Analyzes the price's deviation from VWAP for mean-reversion signals."""
        required_cols = [self.vwap_col, self.upper_col, self.lower_col, self.zscore_col]
        
        # ✨ Bias-Free Analysis
        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 1:
            return {"status": "Insufficient Data", "analysis": {}}

        last = valid_df.iloc[-1]
        
        close_price = last['close']
        vwap = last[self.vwap_col]
        upper = last[self.upper_col]
        lower = last[self.lower_col]
        z_score = last[self.zscore_col]

        # --- Mean Reversion Signal Logic ---
        position = "Inside Bands"
        signal = "Hold"
        message = "Price is within the VWAP standard deviation bands."
        
        # Price above the upper band suggests it's overextended and may revert down (Sell signal for mean reversion)
        if close_price > upper:
            position = "Overextended Above"
            signal = "Sell"
            message = f"Price is overextended above the upper band (Z-score: {round(z_score, 2)}). Potential reversion downwards."
        # Price below the lower band suggests it's oversold and may revert up (Buy signal for mean reversion)
        elif close_price < lower:
            position = "Overextended Below"
            signal = "Buy"
            message = f"Price is overextended below the lower band (Z-score: {round(z_score, 2)}). Potential reversion upwards."

        return {
            "status": "OK",
            "reset_period": self.reset_period,
            "values": {
                "vwap": round(vwap, 5),
                "upper_band": round(upper, 5),
                "lower_band": round(lower, 5),
                "bandwidth_percent": round(last.get(self.bandwidth_col, 0), 2),
                "z_score": round(z_score, 2)
            },
            "analysis": {
                "position": position,
                "signal": signal, # Mean-reversion signal
                "message": message
            }
        }
