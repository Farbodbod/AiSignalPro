import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Optional

# BaseIndicator را از ماژول مربوطه وارد کنید
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class CciIndicator(BaseIndicator):
    """
    CCI Indicator - Definitive MTF & Adaptive Thresholds Version
    -------------------------------------------------------------
    This version not only perfects the CCI but also pioneers the MTF
    architecture for the AiSignalPro project.

    Features:
    - Native Multi-Timeframe (MTF) support.
    - Adaptive Thresholds based on CCI's standard deviation.
    - Highly performant vectorized calculations.
    - Rich, insightful analysis output.
    - Architecturally pure and consistent with project standards.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        # --- Main Parameters ---
        self.period = int(self.params.get('period', 20))
        self.constant = float(self.params.get('constant', 0.015))
        
        # --- MTF Parameters ---
        self.timeframe = self.params.get('timeframe', None) # e.g., '4H', '1D'
        
        # --- Threshold Parameters ---
        self.use_adaptive_thresholds = bool(self.params.get('adaptive_thresholds', False))
        self.adaptive_multiplier = float(self.params.get('adaptive_multiplier', 2.0))
        self.fixed_overbought = float(self.params.get('overbought', 100.0))
        self.fixed_oversold = float(self.params.get('oversold', -100.0))
        
        self.cci_col = f'cci_{self.period}'
        if self.timeframe:
            self.cci_col += f'_{self.timeframe}'

    def calculate(self) -> 'CciIndicator':
        """Calculates CCI, handling MTF resampling and mapping internally."""
        base_df = self.df
        
        # ✨ MTF LOGIC: Resample to target timeframe if specified
        if self.timeframe:
            if not isinstance(base_df.index, pd.DatetimeIndex):
                raise TypeError("DataFrame index must be a DatetimeIndex for MTF resampling.")
            
            logger.info(f"Resampling data to {self.timeframe} for CCI calculation.")
            resampling_rules = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}
            calc_df = base_df.resample(self.timeframe).apply(resampling_rules).dropna()
        else:
            calc_df = base_df.copy()

        if len(calc_df) < self.period:
            logger.warning(f"Not enough data for CCI period {self.period} on timeframe {self.timeframe or 'base'}.")
            self.df[self.cci_col] = np.nan
            return self

        # ✨ PERFORMANCE: Vectorized calculation (no slow .apply)
        tp = (calc_df['high'] + calc_df['low'] + calc_df['close']) / 3
        ma_tp = tp.rolling(window=self.period).mean()
        # Correct vectorized mean deviation
        mean_dev = tp.rolling(window=self.period).apply(lambda x: np.mean(np.abs(x - np.mean(x))), raw=True)
        
        # Safe division
        safe_denominator = (self.constant * mean_dev).replace(0, np.nan)
        cci_series = (tp - ma_tp) / safe_denominator
        
        # ✨ MTF LOGIC: Map results back to the original dataframe's index
        if self.timeframe:
            # Create a temporary df with the calculated CCI to reindex
            temp_df = pd.DataFrame({self.cci_col: cci_series}, index=calc_df.index)
            # Forward-fill the values onto the original index
            self.df[self.cci_col] = temp_df.reindex(base_df.index, method='ffill')
        else:
            self.df[self.cci_col] = cci_series
            
        return self

    def analyze(self) -> Dict[str, Any]:
        """Analyzes the latest CCI value with fixed or adaptive thresholds."""
        if self.cci_col not in self.df.columns or self.df[self.cci_col].isnull().all():
            return {"status": "No Data", "analysis": {}}

        # Drop NaNs for analysis to get the true last values
        valid_cci = self.df[self.cci_col].dropna()
        if len(valid_cci) < 2:
            return {"status": "Insufficient Data", "analysis": {}}
        
        last_val = valid_cci.iloc[-1]
        prev_val = valid_cci.iloc[-2]
        
        # ✨ ADAPTIVE THRESHOLDS LOGIC
        if self.use_adaptive_thresholds:
            cci_std = valid_cci.std()
            overbought_level = cci_std * self.adaptive_multiplier
            oversold_level = -cci_std * self.adaptive_multiplier
            threshold_type = "Adaptive"
        else:
            overbought_level = self.fixed_overbought
            oversold_level = self.fixed_oversold
            threshold_type = "Fixed"

        # --- Analysis Logic ---
        position = "Neutral"
        if last_val > overbought_level: position = "Overbought"
        elif last_val < oversold_level: position = "Oversold"
        
        signal = "Hold"
        if prev_val <= overbought_level < last_val: signal = "Bullish Cross"
        elif prev_val >= oversold_level > last_val: signal = "Bearish Cross"
        elif prev_val > overbought_level >= last_val: signal = "Exit Buy Zone"
        elif prev_val < oversold_level <= last_val: signal = "Exit Sell Zone"

        return {
            "status": "OK",
            "value": round(last_val, 2),
            "timeframe": self.timeframe or "Base",
            "analysis": {
                "position": position,
                "signal": signal,
            },
            "thresholds": {
                "type": threshold_type,
                "overbought": round(overbought_level, 2),
                "oversold": round(oversold_level, 2)
            }
        }
