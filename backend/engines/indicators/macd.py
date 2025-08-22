# backend/engines/indicators/macd.py (v5.0 - The Quantum Momentum Edition)
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class MacdIndicator(BaseIndicator):
    """
    MACD - (v5.0 - The Quantum Momentum Edition)
    -------------------------------------------------------------------
    This world-class version evolves into a quantum momentum engine. It now
    features a normalized histogram for cross-asset comparison, a 0-100
    momentum strength score, and expressive summaries. The architecture is
    fully hardened with data filling and a Sentinel-compliant output.
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
        else: suffix += '_base'
        
        self.macd_col = f'macd{suffix}'
        self.signal_col = f'macd_signal{suffix}'
        self.hist_col = f'macd_hist{suffix}'
        self.hist_norm_col = f'macd_hist_norm{suffix}' # New normalized histogram column

    def calculate(self) -> 'MacdIndicator':
        if len(self.df) < self.slow_period + self.signal_period:
            logger.warning(f"Not enough data for MACD on {self.timeframe or 'base'}.")
            for col in [self.macd_col, self.signal_col, self.hist_col, self.hist_norm_col]:
                self.df[col] = np.nan
            return self

        close_series = pd.to_numeric(self.df['close'], errors='coerce')
        
        ema_fast = close_series.ewm(span=self.fast_period, adjust=False).mean()
        ema_slow = close_series.ewm(span=self.slow_period, adjust=False).mean()
        
        macd_series = ema_fast - ema_slow
        signal_series = macd_series.ewm(span=self.signal_period, adjust=False).mean()
        hist_series = macd_series - signal_series
        
        # ✅ QUANTUM FEATURE: Normalized Histogram for cross-asset comparison
        close_std = close_series.rolling(window=self.slow_period).std().replace(0, np.nan)
        hist_norm_series = hist_series / close_std

        # ✅ HARDENED FILL: Add a limited ffill/bfill for robustness.
        fill_limit = 3
        self.df[self.macd_col] = macd_series.ffill(limit=fill_limit).bfill(limit=2)
        self.df[self.signal_col] = signal_series.ffill(limit=fill_limit).bfill(limit=2)
        self.df[self.hist_col] = hist_series.ffill(limit=fill_limit).bfill(limit=2)
        self.df[self.hist_norm_col] = hist_norm_series.ffill(limit=fill_limit).bfill(limit=2)

        return self

    def analyze(self) -> Dict[str, Any]:
        required_cols = [self.macd_col, self.signal_col, self.hist_col]
        empty_analysis = {"values": {}, "analysis": {}}
        if not all(col in self.df.columns for col in required_cols):
            return {"status": "Calculation Incomplete", **empty_analysis}

        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 2:
            return {"status": "Insufficient Data", **empty_analysis}

        last, prev = valid_df.iloc[-1], valid_df.iloc[-2]
        
        signal = "Neutral"
        if prev[self.macd_col] <= prev[self.signal_col] and last[self.macd_col] > last[self.signal_col]: signal = "Bullish Crossover"
        elif prev[self.macd_col] >= prev[self.signal_col] and last[self.macd_col] < last[self.signal_col]: signal = "Bearish Crossover"
        elif prev[self.macd_col] <= 0 and last[self.macd_col] > 0: signal = "Bullish Centerline Cross"
        elif prev[self.macd_col] >= 0 and last[self.macd_col] < 0: signal = "Bearish Centerline Cross"
            
        trend = "Uptrend" if last[self.macd_col] > 0 else "Downtrend"
        hist_change = last[self.hist_col] - prev[self.hist_col]
        
        momentum = "Neutral"
        if last[self.hist_col] > 0: momentum = "Increasing" if hist_change > 0 else "Decreasing"
        elif last[self.hist_col] < 0: momentum = "Increasing" if hist_change < 0 else "Decreasing" # Note: Increasing momentum when hist is negative means hist_change is negative
        
        # ✅ QUANTUM FEATURE: Signal Strength Score
        max_hist_abs = valid_df[self.hist_col].abs().rolling(window=50).max().iloc[-1]
        strength = min(100, int(abs(last[self.hist_col]) * 100 / (max_hist_abs + 1e-9)))

        # ✅ EXPRESSIVE SUMMARY
        summary = f"Signal: {signal} | Trend: {trend} | Momentum: {momentum} (Strength: {strength}%)"
        if strength > 70 and "Crossover" in signal:
            summary = f"Strong {signal.replace(' Crossover', '')} Reversal forming (MACD crossover with accelerating histogram)"
        elif "Decreasing" in momentum:
            summary = f"{trend} is losing momentum (histogram is shrinking)"
        
        values_content = {
            "macd_line": round(last[self.macd_col], 5), "signal_line": round(last[self.signal_col], 5),
            "histogram": round(last[self.hist_col], 5), "histogram_normalized": round(last.get(self.hist_norm_col, 0), 3)
        }
        analysis_content = {
            "signal": signal, "strength": strength,
            "context": {"trend": trend, "momentum": momentum}, "summary": summary
        }

        return {
            "status": "OK", "timeframe": self.timeframe or 'Base',
            "values": values_content, "analysis": analysis_content
        }
