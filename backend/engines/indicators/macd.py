import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

# اطمینان حاصل کنید که این اندیکاتور از فایل مربوطه وارد شده‌ است
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class MacdIndicator(BaseIndicator):
    """
    MACD - Definitive, MTF, and Advanced Momentum Analysis World-Class Version
    --------------------------------------------------------------------------
    This version provides a comprehensive momentum and trend analysis engine.
    It goes beyond simple crossovers to analyze the underlying trend direction,
    momentum strength, and momentum acceleration (histogram change), all
    within the standard AiSignalPro MTF architecture.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        # --- Parameters ---
        self.params = kwargs.get('params', {})
        self.fast_period = int(self.params.get('fast_period', 12))
        self.slow_period = int(self.params.get('slow_period', 26))
        self.signal_period = int(self.params.get('signal_period', 9))
        self.timeframe = self.params.get('timeframe', None)

        if not self.fast_period < self.slow_period:
            raise ValueError("fast_period must be less than slow_period.")

        # --- Dynamic Column Naming ---
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
        """Orchestrates the MTF calculation for MACD."""
        base_df = self.df
        
        # ✨ MTF LOGIC: Resample data if a timeframe is specified
        if self.timeframe:
            if not isinstance(base_df.index, pd.DatetimeIndex):
                raise TypeError("DataFrame index must be a DatetimeIndex for MTF.")
            rules = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}
            calc_df = base_df.resample(self.timeframe, label='right', closed='right').apply(rules).dropna()
        else:
            calc_df = base_df.copy()

        if len(calc_df) < self.slow_period + self.signal_period:
            logger.warning(f"Not enough data for MACD on timeframe {self.timeframe or 'base'}.")
            return self

        macd_results = self._calculate_macd(calc_df)
        
        # --- Map results back to the original dataframe if MTF ---
        if self.timeframe:
            final_results = macd_results.reindex(base_df.index, method='ffill')
            for col in final_results.columns: self.df[col] = final_results[col]
        else:
            for col in macd_results.columns: self.df[col] = macd_results[col]

        return self

    def analyze(self) -> Dict[str, Any]:
        """Provides a deep, bias-free analysis of the trend and momentum."""
        required_cols = [self.macd_col, self.signal_col, self.hist_col]
        
        # ✨ Bias-Free: Drop all NaNs first
        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 2:
            return {"status": "Insufficient Data", "analysis": {}}

        # ✨ Bias-Free: Analyze the last fully closed candle's data
        last = valid_df.iloc[-1]
        prev = valid_df.iloc[-2]

        # --- 1. Primary Crossover Signal ---
        signal = "Neutral"
        # Signal Line Crossover
        if prev[self.macd_col] <= prev[self.signal_col] and last[self.macd_col] > last[self.signal_col]:
            signal = "Bullish Crossover"
        elif prev[self.macd_col] >= prev[self.signal_col] and last[self.macd_col] < last[self.signal_col]:
            signal = "Bearish Crossover"
        # Centerline Crossover
        elif prev[self.macd_col] <= 0 and last[self.macd_col] > 0:
            signal = "Bullish Centerline Cross"
        elif prev[self.macd_col] >= 0 and last[self.macd_col] < 0:
            signal = "Bearish Centerline Cross"
            
        # --- 2. Deep Contextual Analysis for Automation ---
        # Overall Trend Direction
        trend = "Uptrend" if last[self.macd_col] > 0 else "Downtrend"
        
        # Momentum State (Acceleration/Deceleration)
        momentum = "Neutral"
        hist_change = last[self.hist_col] - prev[self.hist_col]
        if last[self.hist_col] > 0: # Bullish momentum
            momentum = "Increasing" if hist_change > 0 else "Decreasing"
        elif last[self.hist_col] < 0: # Bearish momentum
            momentum = "Increasing" if hist_change < 0 else "Decreasing" # Increasing in negative direction

        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "values": {
                "macd_line": round(last[self.macd_col], 5),
                "signal_line": round(last[self.signal_col], 5),
                "histogram": round(last[self.hist_col], 5),
            },
            "analysis": {
                "signal": signal, # The primary event
                "context": {
                    "trend": trend,
                    "momentum": momentum
                },
                "summary": f"Signal: {signal} | Trend: {trend} | Momentum: {momentum}"
            }
        }
