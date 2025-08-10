import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class CciIndicator(BaseIndicator):
    """
    CCI Indicator - Definitive, World-Class Version (v4.0 - Final Architecture)
    --------------------------------------------------------------------------
    This version adheres to the final AiSignalPro architecture. It performs its
    calculations on the pre-resampled dataframe provided by the IndicatorAnalyzer,
    making it a pure, efficient, and powerful momentum analysis engine with
    adaptive threshold capabilities.
    """
    dependencies: list = [] # CCI has no internal dependencies

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.period = int(self.params.get('period', 20))
        self.constant = float(self.params.get('constant', 0.015))
        self.timeframe = self.params.get('timeframe', None)
        self.use_adaptive_thresholds = bool(self.params.get('use_adaptive_thresholds', True))
        self.adaptive_multiplier = float(self.params.get('adaptive_multiplier', 2.0))
        self.fixed_overbought = float(self.params.get('overbought', 100.0))
        self.fixed_oversold = float(self.params.get('oversold', -100.0))
        
        suffix = f'_{self.period}'
        if self.timeframe:
            suffix += f'_{self.timeframe}'
        self.cci_col = f'cci{suffix}'

    def calculate(self) -> 'CciIndicator':
        """
        ✨ FINAL ARCHITECTURE: No resampling. Just pure calculation.
        The dataframe received is already at the correct timeframe.
        """
        df_for_calc = self.df
        
        if len(df_for_calc) < self.period:
            logger.warning(f"Not enough data for CCI period {self.period} on timeframe {self.timeframe or 'base'}.")
            self.df[self.cci_col] = np.nan
            return self

        tp = (df_for_calc['high'] + df_for_calc['low'] + df_for_calc['close']) / 3
        ma_tp = tp.rolling(window=self.period).mean()
        # Note: .apply() can be slow on very large datasets, but is correct.
        mean_dev = tp.rolling(window=self.period).apply(lambda x: np.mean(np.abs(x - np.mean(x))), raw=True)
        
        safe_denominator = (self.constant * mean_dev).replace(0, np.nan)
        self.df[self.cci_col] = (tp - ma_tp) / safe_denominator
            
        return self

    def analyze(self) -> Dict[str, Any]:
        """
        Analyzes the latest CCI value with fixed or adaptive thresholds.
        This powerful analysis logic remains unchanged.
        """
        if self.cci_col not in self.df.columns or self.df[self.cci_col].isnull().all():
            return {"status": "No Data", "analysis": {}}

        valid_cci = self.df[self.cci_col].dropna()
        if len(valid_cci) < 2:
            return {"status": "Insufficient Data", "analysis": {}}
        
        last_val = valid_cci.iloc[-1]
        prev_val = valid_cci.iloc[-2]
        
        if self.use_adaptive_thresholds:
            cci_std = valid_cci.std()
            overbought_level = cci_std * self.adaptive_multiplier
            oversold_level = -cci_std * self.adaptive_multiplier
            threshold_type = "Adaptive"
        else:
            overbought_level = self.fixed_overbought
            oversold_level = self.fixed_oversold
            threshold_type = "Fixed"

        position = "Neutral"
        if last_val > overbought_level: position = "Overbought"
        elif last_val < oversold_level: position = "Oversold"
        
        signal = "Hold"
        if prev_val <= oversold_level and last_val > oversold_level: signal = "Bullish Crossover"
        elif prev_val >= overbought_level and last_val < overbought_level: signal = "Bearish Crossover"
        elif prev_val > oversold_level and last_val <= oversold_level: signal = "Enter Sell Zone"
        elif prev_val < overbought_level and last_val >= overbought_level: signal = "Enter Buy Zone"

        return {
            "status": "OK",
            "timeframe": self.timeframe or "Base",
            "values": {
                "cci": round(last_val, 2)
            },
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
