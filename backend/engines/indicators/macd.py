import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class MacdIndicator(BaseIndicator):
    """
    MACD - Definitive, World-Class Version (v4.0 - Final Architecture)
    -------------------------------------------------------------------
    This version provides a comprehensive momentum and trend analysis engine.
    It adheres to the final AiSignalPro architecture by performing its
    calculations on the pre-resampled dataframe provided by the IndicatorAnalyzer.
    """
    dependencies: list = []

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.fast_period = int(self.params.get('fast_period', 12))
        self.slow_period = int(self.params.get('slow_period', 26))
        self.signal_period = int(self.params.get('signal_period', 9))
        self.timeframe = self.params.get('timeframe', None)

        if not self.fast_period < self.slow_period:
            raise ValueError("fast_period must be less than slow_period.")

        suffix = f'_{self.fast_period}_{self.slow_period}_{self.signal_period}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.macd_col = f'macd{suffix}'
        self.signal_col = f'macd_signal{suffix}'
        self.hist_col = f'macd_hist{suffix}'

    def _calculate_macd(self, df: pd.DataFrame) -> pd.DataFrame:
        """The core, technically correct MACD calculation logic."""
        res = pd.DataFrame(index=df.index)
        close_series = pd.to_numeric(df['close'], errors='coerce')
        
        ema_fast = close_series.ewm(span=self.fast_period, adjust=False).mean()
        ema_slow = close_series.ewm(span=self.slow_period, adjust=False).mean()
        
        res[self.macd_col] = ema_fast - ema_slow
        res[self.signal_col] = res[self.macd_col].ewm(span=self.signal_period, adjust=False).mean()
        res[self.hist_col] = res[self.macd_col] - res[self.signal_col]
        return res

    def calculate(self) -> 'MacdIndicator':
        """
        ✨ FINAL ARCHITECTURE: No resampling. Just pure calculation.
        The dataframe received is already at the correct timeframe.
        """
        df_for_calc = self.df
        
        if len(df_for_calc) < self.slow_period + self.signal_period:
            logger.warning(f"Not enough data for MACD on timeframe {self.timeframe or 'base'}.")
            for col in [self.macd_col, self.signal_col, self.hist_col]:
                self.df[col] = np.nan
            return self

        macd_results = self._calculate_macd(df_for_calc)
        
        for col in macd_results.columns:
            self.df[col] = macd_results[col]

        return self

    def analyze(self) -> Dict[str, Any]:
        """
        Provides a deep, bias-free analysis of the trend and momentum.
        This powerful analysis logic remains unchanged.
        """
        required_cols = [self.macd_col, self.signal_col, self.hist_col]
        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 2:
            return {"status": "Insufficient Data", "analysis": {}}

        last = valid_df.iloc[-1]
        prev = valid_df.iloc[-2]

        signal = "Neutral"
        if prev[self.macd_col] <= prev[self.signal_col] and last[self.macd_col] > last[self.signal_col]:
            signal = "Bullish Crossover"
        elif prev[self.macd_col] >= prev[self.signal_col] and last[self.macd_col] < last[self.signal_col]:
            signal = "Bearish Crossover"
        elif prev[self.macd_col] <= 0 and last[self.macd_col] > 0:
            signal = "Bullish Centerline Cross"
        elif prev[self.macd_col] >= 0 and last[self.macd_col] < 0:
            signal = "Bearish Centerline Cross"
            
        trend = "Uptrend" if last[self.macd_col] > 0 else "Downtrend"
        
        momentum = "Neutral"
        hist_change = last[self.hist_col] - prev[self.hist_col]
        if last[self.hist_col] > 0:
            momentum = "Increasing" if hist_change > 0 else "Decreasing"
        elif last[self.hist_col] < 0:
            momentum = "Increasing" if hist_change < 0 else "Decreasing"

        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "values": {
                "macd_line": round(last[self.macd_col], 5),
                "signal_line": round(last[self.signal_col], 5),
                "histogram": round(last[self.hist_col], 5),
            },
            "analysis": {
                "signal": signal,
                "context": {
                    "trend": trend,
                    "momentum": momentum
                },
                "summary": f"Signal: {signal} | Trend: {trend} | Momentum: {momentum}"
            }
        }
