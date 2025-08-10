import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Optional

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class FastMAIndicator(BaseIndicator):
    """
    Fast MA (DEMA/TEMA) - Definitive, World-Class Version (v4.1 - Harmonized Edition)
    ----------------------------------------------------------------------------------
    This version provides a world-class implementation of DEMA and TEMA, featuring
    advanced momentum analysis (slope and acceleration). It adheres to the final
    AiSignalPro architecture by calculating on the pre-resampled dataframe.
    Includes defensive programming to prevent AttributeErrors.
    """
    dependencies: list = []

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.period = int(self.params.get('period', 14))
        self.ma_type = str(self.params.get('ma_type', 'DEMA')).upper()
        
        # FIX: Ensure timeframe is always initialized, even if None
        self.timeframe = self.params.get('timeframe', None)
        
        self.slope_threshold = float(self.params.get('slope_threshold', 0.0005)) # 0.05%

        if self.period < 1: raise ValueError("Period must be a positive integer.")
        if self.ma_type not in ['DEMA', 'TEMA']: raise ValueError("ma_type must be 'DEMA' or 'TEMA'.")
        
        suffix = f'_{self.period}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.ma_col = f'{self.ma_type.lower()}{suffix}'

    # ... (rest of the code remains the same) ...
    # The fix is in __init__.

    def _calculate_fast_ma(self, df: pd.DataFrame) -> pd.DataFrame:
        """The core, technically correct DEMA/TEMA calculation logic."""
        res = pd.DataFrame(index=df.index)
        close_series = pd.to_numeric(df['close'], errors='coerce')
        
        ema1 = close_series.ewm(span=self.period, adjust=False).mean()
        ema2 = ema1.ewm(span=self.period, adjust=False).mean()
        
        if self.ma_type == 'DEMA':
            res[self.ma_col] = 2 * ema1 - ema2
        elif self.ma_type == 'TEMA':
            ema3 = ema2.ewm(span=self.period, adjust=False).mean()
            res[self.ma_col] = 3 * ema1 - 3 * ema2 + ema3
            
        return res

    def calculate(self) -> 'FastMAIndicator':
        """
        ✨ FINAL ARCHITECTURE: No resampling. Just pure calculation.
        The dataframe received is already at the correct timeframe.
        """
        df_for_calc = self.df
        
        # A safe margin for TEMA which uses EMA of EMA of EMA
        if len(df_for_calc) < self.period * 3:
            logger.warning(f"Not enough data for {self.ma_type} on timeframe {self.timeframe or 'base'}.")
            self.df[self.ma_col] = np.nan
            return self

        ma_results = self._calculate_fast_ma(df_for_calc)
        
        self.df[self.ma_col] = ma_results[self.ma_col]

        return self

    def analyze(self) -> Dict[str, Any]:
        """
        Provides a deep, bias-free analysis of the trend's momentum and acceleration.
        This powerful analysis logic remains unchanged.
        """
        valid_df = self.df.dropna(subset=[self.ma_col, 'close'])
        if len(valid_df) < 3: # Need at least 3 points to calculate acceleration
            return {"status": "Insufficient Data", "analysis": {}}

        last = valid_df.iloc[-1]
        prev = valid_df.iloc[-2]
        prev_prev = valid_df.iloc[-3]

        close_price = last['close']
        ma_val = last[self.ma_col]
        
        slope = ma_val - prev[self.ma_col]
        prev_slope = prev[self.ma_col] - prev_prev[self.ma_col]
        acceleration = slope - prev_slope
        
        signal = "Neutral"; message = "No clear momentum signal."
        
        is_bullish = close_price > ma_val and slope > (abs(ma_val) * self.slope_threshold)
        is_bearish = close_price < ma_val and slope < -(abs(ma_val) * self.slope_threshold)

        if is_bullish:
            signal = "Buy"
            strength = "Accelerating" if acceleration > 0 else "Decelerating"
            message = f"Bullish trend ({strength}). Price is above {self.ma_type} and slope is positive."
        elif is_bearish:
            signal = "Sell"
            strength = "Accelerating" if acceleration < 0 else "Decelerating"
            message = f"Bearish trend ({strength}). Price is below {self.ma_type} and slope is negative."

        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "indicator_type": self.ma_type,
            "values": {
                "ma_value": round(ma_val, 5),
                "price": round(close_price, 5),
            },
            "analysis": {
                "signal": signal,
                "slope": round(slope, 5),
                "acceleration": round(acceleration, 5),
                "message": message
            }
        }
