import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

# اطمینان حاصل کنید که این اندیکاتور از فایل مربوطه وارد شده‌ است
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class BollingerIndicator(BaseIndicator):
    """
    Bollinger Bands - Definitive, Trading-Safe, MTF & World-Class Version
    ----------------------------------------------------------------------
    This version is the final standard for the AiSignalPro project, featuring:
    - Technically precise calculations (std with ddof=0) for cross-platform consistency.
    - Bias-free analysis logic, safe for backtesting and live trading.
    - The standard, encapsulated MTF architecture.
    - Advanced, configurable volatility squeeze detection.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        # --- Parameters ---
        self.params = kwargs.get('params', {})
        self.period = int(self.params.get('period', 20))
        self.std_dev = float(self.params.get('std_dev', 2.0))
        self.timeframe = self.params.get('timeframe', None)
        self.squeeze_lookback = int(self.params.get('squeeze_lookback', 120))
        self.squeeze_threshold = float(self.params.get('squeeze_threshold', 1.1))

        # --- Dynamic Column Naming ---
        suffix = f'_{self.period}_{self.std_dev}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.middle_col = f'bb_middle{suffix}'
        self.upper_col = f'bb_upper{suffix}'
        self.lower_col = f'bb_lower{suffix}'
        self.width_col = f'bb_width{suffix}'
        self.percent_b_col = f'bb_percent_b{suffix}'

    def _calculate_bb(self, df: pd.DataFrame) -> pd.DataFrame:
        """The core, technically correct Bollinger Bands calculation logic."""
        res = pd.DataFrame(index=df.index)
        
        middle = df['close'].rolling(window=self.period).mean()
        # ✨ Technical Correction: Use ddof=0 for consistency with platforms like TradingView
        std = df['close'].rolling(window=self.period).std(ddof=0)
        
        upper = middle + (std * self.std_dev)
        lower = middle - (std * self.std_dev)
        
        # Safe division for width and %B
        safe_middle = middle.replace(0, np.nan)
        safe_range = (upper - lower).replace(0, np.nan)
        
        width = (upper - lower) / safe_middle * 100
        percent_b = (df['close'] - lower) / safe_range
        
        res[self.middle_col] = middle
        res[self.upper_col] = upper
        res[self.lower_col] = lower
        res[self.width_col] = width
        res[self.percent_b_col] = percent_b
        return res

    def calculate(self) -> 'BollingerIndicator':
        """Orchestrates the MTF calculation for Bollinger Bands."""
        base_df = self.df
        
        # ✨ MTF LOGIC: Resample data if a timeframe is specified
        if self.timeframe:
            if not isinstance(base_df.index, pd.DatetimeIndex):
                raise TypeError("DataFrame index must be a DatetimeIndex for MTF.")
            rules = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}
            calc_df = base_df.resample(self.timeframe, label='right', closed='right').apply(rules).dropna()
        else:
            calc_df = base_df.copy()

        if len(calc_df) < self.period:
            logger.warning(f"Not enough data for Bollinger Bands on timeframe {self.timeframe or 'base'}.")
            return self

        bb_results = self._calculate_bb(calc_df)
        
        # --- Map results back to the original dataframe if MTF ---
        if self.timeframe:
            final_results = bb_results.reindex(base_df.index, method='ffill')
            for col in final_results.columns: self.df[col] = final_results[col]
        else:
            for col in bb_results.columns: self.df[col] = bb_results[col]

        return self

    def analyze(self) -> Dict[str, Any]:
        """Provides a bias-free analysis, safe for backtesting and live trading."""
        required_cols = [self.middle_col, self.width_col, self.percent_b_col]
        
        # ✨ Bias-Free: Drop all NaNs first to get a clean series for analysis
        valid_df = self.df.dropna(subset=required_cols)
        
        if len(valid_df) < self.squeeze_lookback:
            return {"status": "Insufficient Data", "analysis": {}}

        # ✨ Bias-Free: Analyze the last fully closed candle's data
        last_row = valid_df.iloc[-1]
        
        # --- Squeeze Detection ---
        lowest_width = valid_df[self.width_col].rolling(window=self.squeeze_lookback).min().iloc[-1]
        is_squeeze = last_row[self.width_col] <= (lowest_width * self.squeeze_threshold)
        
        # --- Position Analysis ---
        position = "Inside Bands"
        if last_row[self.percent_b_col] > 1.0: position = "Breakout Above"
        elif last_row[self.percent_b_col] < 0.0: position = "Breakdown Below"
        elif last_row[self.percent_b_col] == 1.0: position = "Touching Upper Band"
        elif last_row[self.percent_b_col] == 0.0: position = "Touching Lower Band"

        signal = "Squeeze" if is_squeeze else position
        
        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "values": {
                "upper_band": round(last_row[self.upper_col], 5),
                "middle_band": round(last_row[self.middle_col], 5),
                "lower_band": round(last_row[self.lower_col], 5),
                "bandwidth": round(last_row[self.width_col], 4),
                "percent_b": round(last_row[self.percent_b_col], 3),
            },
            "analysis": {
                "is_squeeze": is_squeeze,
                "position": position,
                "signal": signal
            }
        }
