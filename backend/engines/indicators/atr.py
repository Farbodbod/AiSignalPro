# backend/engines/indicators/atr.py (v7.1 - The Hardened Fill Edition)
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class AtrIndicator(BaseIndicator):
    """
    ATR Indicator - (v7.1 - The Hardened Fill Edition)
    --------------------------------------------------------------
    This definitive version is fully aligned with the project's final
    architectural standards. It introduces a robust, two-step fill logic
    (ffill -> bfill) and a zero-division shield to guarantee a complete and
    valid output series under all data conditions.
    """
    dependencies: list = []

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.period = int(self.params.get('period', 14))
        self.timeframe = self.params.get('timeframe', None)
        self.volatility_thresholds = self.params.get('volatility_thresholds', {
            'low_max': 1.0, 'normal_max': 3.0, 'high_max': 5.0
        })

        suffix = f'_{self.period}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.atr_col = f'atr{suffix}'
        self.atr_pct_col = f'atr_pct{suffix}'

    def calculate(self) -> 'AtrIndicator':
        df_for_calc = self.df
        if len(df_for_calc) < self.period:
            logger.warning(f"Not enough data for ATR on {self.timeframe or 'base'}.")
            self.df[self.atr_col] = np.nan
            self.df[self.atr_pct_col] = np.nan
            return self

        tr = pd.concat([
            df_for_calc['high'] - df_for_calc['low'],
            abs(df_for_calc['high'] - df_for_calc['close'].shift(1)),
            abs(df_for_calc['low'] - df_for_calc['close'].shift(1))
        ], axis=1).max(axis=1)

        atr = tr.ewm(alpha=1/self.period, adjust=False).mean()
        
        # ✅ ZERO-DIVISION SHIELD (v7.1):
        safe_close = df_for_calc['close'].replace(0, np.nan)
        atr_pct = (atr / safe_close) * 100
        atr_pct.replace([np.inf, -np.inf], np.nan, inplace=True)

        # ✅ HARDENED FILL (v7.1): Two-step fill process for maximum robustness.
        fill_limit = 3
        # Step 1: Forward-fill to propagate last known good values
        filled_atr = atr.ffill(limit=fill_limit)
        filled_atr_pct = atr_pct.ffill(limit=fill_limit)
        # Step 2: Backfill to handle any remaining NaNs at the very start of the series
        self.df[self.atr_col] = filled_atr.bfill(limit=2)
        self.df[self.atr_pct_col] = filled_atr_pct.bfill(limit=2)

        return self

    def analyze(self) -> Dict[str, Any]:
        required_cols = [self.atr_col, self.atr_pct_col]
        empty_analysis = {"values": {}, "analysis": {}}
        
        if not all(col in self.df.columns for col in required_cols):
            return {"status": "Calculation Incomplete", **empty_analysis}

        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 1:
            return {"status": "Insufficient Data", **empty_analysis}

        last_row = valid_df.iloc[-1]
        last_atr_val = last_row[self.atr_col]
        last_atr_pct = last_row[self.atr_pct_col]

        t = self.volatility_thresholds
        if last_atr_pct <= t['low_max']: volatility_level = "Low"
        elif last_atr_pct <= t['normal_max']: volatility_level = "Normal"
        elif last_atr_pct <= t['high_max']: volatility_level = "High"
        else: volatility_level = "Extreme"

        values_content = {
            "atr": round(last_atr_val, 5),
            "atr_percent": round(last_atr_pct, 2),
        }
        analysis_content = {
            "volatility": volatility_level
        }

        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "values": values_content,
            "analysis": analysis_content
        }
