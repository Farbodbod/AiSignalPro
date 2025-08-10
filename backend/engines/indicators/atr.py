import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Optional

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class AtrIndicator(BaseIndicator):
    """
    ATR Indicator - Definitive, World-Class Version (v4.1 - Harmonized Edition)
    ---------------------------------------------------------------------------
    This version includes a standardized naming convention for its output columns,
    ensuring seamless integration with other dependent indicators like SuperTrend and Chandelier Exit.
    """
    dependencies: list = []

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

        # FIX: Use the new standardized method for column names
        self.atr_col = self._get_atr_col_name(self.period, self.timeframe)
        self.atr_pct_col = f'atr_pct_{self.period}'
        if self.timeframe: self.atr_pct_col += f'_{self.timeframe}'
        
    @staticmethod
    def _get_atr_col_name(period: int, timeframe: Optional[str] = None) -> str:
        """
        Provides a standardized way to generate the ATR column name.
        This method will be used by all dependent indicators to ensure consistency.
        """
        name = f'atr_{period}'
        if timeframe:
            name += f'_{timeframe}'
        return name

    def calculate(self) -> 'AtrIndicator':
        """
        ✨ FINAL ARCHITECTURE: No resampling. Just pure calculation.
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
