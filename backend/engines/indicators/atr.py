import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class AtrIndicator(BaseIndicator):
    """
    ATR Indicator - Definitive, World-Class Version (v4.0 - Final Architecture)
    ---------------------------------------------------------------------------
    This version adheres to the final AiSignalPro architecture. It performs its
    calculations on the pre-resampled dataframe provided by the IndicatorAnalyzer,
    making it a pure, efficient, and powerful volatility analysis engine.
    """
    dependencies: list = [] # ATR has no internal dependencies on other indicators

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.period = int(self.params.get('period', 14))
        self.timeframe = self.params.get('timeframe', None)
        self.volatility_thresholds = self.params.get('volatility_thresholds', {
            'low_max': 1.0,
            'normal_max': 3.0,
            'high_max': 5.0
        })

        suffix = f'_{self.period}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.atr_col = f'atr{suffix}'
        self.atr_pct_col = f'atr_pct{suffix}'

    def calculate(self) -> 'AtrIndicator':
        """
        ✨ FINAL ARCHITECTURE: No resampling. Just pure calculation.
        The dataframe received is already at the correct timeframe.
        """
        df_for_calc = self.df
        
        if len(df_for_calc) < self.period:
            logger.warning(f"Not enough data for ATR on timeframe {self.timeframe or 'base'}.")
            self.df[self.atr_col] = np.nan
            self.df[self.atr_pct_col] = np.nan
            return self
            
        # --- Vectorized Calculation on the pre-resampled dataframe ---
        tr = pd.concat([
            df_for_calc['high'] - df_for_calc['low'],
            np.abs(df_for_calc['high'] - df_for_calc['close'].shift(1)),
            np.abs(df_for_calc['low'] - df_for_calc['close'].shift(1))
        ], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1/self.period, adjust=False).mean()
        
        safe_close = df_for_calc['close'].replace(0, np.nan)
        atr_pct = (atr / safe_close) * 100
        
        # Add the final columns directly to the dataframe
        self.df[self.atr_col] = atr
        self.df[self.atr_pct_col] = atr_pct
        
        return self

    def analyze(self) -> Dict[str, Any]:
        """
        Provides an intelligent classification of the current market volatility.
        This powerful analysis logic remains unchanged.
        """
        required_cols = [self.atr_col, self.atr_pct_col]
        valid_df = self.df.dropna(subset=required_cols)
        
        if len(valid_df) < 1:
            return {"status": "Insufficient Data", "timeframe": self.timeframe or 'Base'}
        
        last_row = valid_df.iloc[-1]
        last_atr_val = last_row[self.atr_col]
        last_atr_pct = last_row[self.atr_pct_col]
        
        # --- Volatility Level Analysis ---
        t = self.volatility_thresholds
        if last_atr_pct <= t['low_max']: volatility_level = "Low"
        elif last_atr_pct <= t['normal_max']: volatility_level = "Normal"
        elif last_atr_pct <= t['high_max']: volatility_level = "High"
        else: volatility_level = "Extreme"

        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "values": {
                "atr": round(last_atr_val, 5),
                "atr_percent": round(last_atr_pct, 2),
            },
            "analysis": {
                "volatility": volatility_level
            }
        }
