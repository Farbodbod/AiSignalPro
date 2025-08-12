import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Optional

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class AtrIndicator(BaseIndicator):
    """
    ATR Indicator - (v6.0 - Harmonized API)
    --------------------------------------------------------------
    This version introduces the standardized `get_col_name` static method, creating
    a robust and unbreakable contract with all dependent indicators within the
    Multi-Version Engine. It is the final piece of the ATR supply chain puzzle.
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

        # ✅ HARMONIZED: Column names are now generated using the official static methods
        self.atr_col = AtrIndicator.get_col_name(self.params, self.timeframe)
        self.atr_pct_col = AtrIndicator.get_atr_pct_col_name(self.params, self.timeframe)

        # --- Real-Time state variables (logic remains unchanged) ---
        self.prev_close = None; self.atr_rt = None; self._tr_sum = 0.0; self._initial_count = 0

    @staticmethod
    def get_col_name(params: Dict[str, Any], timeframe: Optional[str] = None) -> str:
        """ ✅ NEW: The official, standardized method for generating the ATR column name. """
        period = params.get('period', 14)
        name = f'atr_{period}'
        if timeframe:
            name += f'_{timeframe}'
        return name

    @staticmethod
    def get_atr_pct_col_name(params: Dict[str, Any], timeframe: Optional[str] = None) -> str:
        """ ✅ NEW: The official, standardized method for the ATR percent column name. """
        period = params.get('period', 14)
        name = f'atr_pct_{period}'
        if timeframe:
            name += f'_{timeframe}'
        return name

    def calculate(self) -> 'AtrIndicator':
        """ Core calculation logic is unchanged and robust. """
        df_for_calc = self.df

        if len(df_for_calc) < self.period:
            logger.warning(f"Not enough data for ATR on timeframe {self.timeframe or 'base'}.")
            self.df[self.atr_col] = np.nan
            self.df[self.atr_pct_col] = np.nan
            return self

        tr = pd.concat([
            df_for_calc['high'] - df_for_calc['low'],
            abs(df_for_calc['high'] - df_for_calc['close'].shift(1)),
            abs(df_for_calc['low'] - df_for_calc['close'].shift(1))
        ], axis=1).max(axis=1)

        atr = tr.ewm(alpha=1/self.period, adjust=False).mean()

        safe_close = df_for_calc['close'].replace(0, np.nan)
        atr_pct = (atr / safe_close) * 100

        self.df[self.atr_col] = atr
        self.df[self.atr_pct_col] = atr_pct

        return self

    def update_realtime(self, high: float, low: float, close: float) -> Optional[float]:
        # Real-time update logic remains unchanged
        if self.prev_close is None: tr = high - low
        else: tr = max(high - low, abs(high - self.prev_close), abs(low - self.prev_close))
        self.prev_close = close
        if self._initial_count < self.period:
            self._tr_sum += tr
            self._initial_count += 1
            if self._initial_count == self.period: self.atr_rt = self._tr_sum / self.period
            return self.atr_rt
        self.atr_rt = (self.atr_rt * (self.period - 1) + tr) / self.period
        return self.atr_rt

    def analyze(self) -> Dict[str, Any]:
        """ Analysis logic remains unchanged and robust. """
        required_cols = [self.atr_col, self.atr_pct_col]
        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 1:
            return {"status": "Insufficient Data"}

        last_row = valid_df.iloc[-1]
        last_atr_val = last_row[self.atr_col]
        last_atr_pct = last_row[self.atr_pct_col]

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
