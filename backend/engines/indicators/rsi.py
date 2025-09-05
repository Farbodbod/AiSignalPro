# backend/engines/indicators/rsi.py (v8.1.0 - Explicit Contract Edition)
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class RsiIndicator(BaseIndicator):
    """
    RSI Indicator - (v8.1.0 - Explicit Contract Edition)
    -------------------------------------------------------------------------------------
    This version implements the "Explicit Contract" principle. The indicator now
    reports the name of its primary data column ('main_col') within the analysis
    output's '_meta' key. This allows consuming frameworks like BaseStrategy to
    directly and reliably access the historical data series without guessing,
    creating a robust, error-proof integration.
    """
    dependencies: list = []

    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], **kwargs):
        super().__init__(df, params=params, **kwargs)
        self.period = int(self.params.get('period', 14))
        self.timeframe = self.params.get('timeframe')
        self.rsi_col = f'RSI_{self.period}'
        self.signal_col = f'RSI_signal_{self.period}'

    def calculate(self) -> 'RsiIndicator':
        """
        Calculates the RSI value using the standard Wilder's smoothing method.
        """
        if len(self.df) < self.period:
            logger.warning(f"Not enough data for RSI on timeframe {self.timeframe or 'base'}.")
            self.df[self.rsi_col] = np.nan
            return self

        delta = self.df['close'].diff()
        gain = delta.where(delta > 0, 0).fillna(0)
        loss = -delta.where(delta < 0, 0).fillna(0)

        avg_gain = gain.ewm(com=self.period - 1, min_periods=self.period).mean()
        avg_loss = loss.ewm(com=self.period - 1, min_periods=self.period).mean()

        rs = avg_gain / avg_loss.replace(0, 1e-9) # Avoid division by zero
        rsi = 100 - (100 / (1 + rs))
        
        self.df[self.rsi_col] = rsi
        self.df[self.signal_col] = rsi.ewm(span=9, adjust=False).mean()

        return self

    def analyze(self) -> Dict[str, Any]:
        """ Provides analysis on RSI levels and intelligent crossover signals. """
        required_cols = [self.rsi_col, self.signal_col]
        # Always return the full object structure for Sentinel compatibility
        empty_analysis = {"values": {}, "analysis": {}}

        if any(col not in self.df.columns for col in required_cols):
            return {"status": "Calculation Incomplete - Columns missing", **empty_analysis}

        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 2:
            return {"status": "Insufficient Data", **empty_analysis}

        # Use the last closed candle (iloc[-1]) as per the Fresh Data Protocol
        last = valid_df.iloc[-1]
        prev = valid_df.iloc[-2]
        
        last_rsi, last_signal = last[self.rsi_col], last[self.signal_col]
        prev_rsi, prev_signal = prev[self.rsi_col], prev[self.signal_col]
        
        oversold, overbought = 30, 70
        position = "Neutral"
        if last_rsi > overbought: position = "Overbought"
        elif last_rsi < oversold: position = "Oversold"
            
        # ✅ NEW: Crossover Intelligence
        crossover_signal = "Hold"
        if prev_rsi < prev_signal and last_rsi >= last_signal:
            crossover_signal = "Bullish Crossover"
        elif prev_rsi > prev_signal and last_rsi <= last_signal:
            crossover_signal = "Bearish Crossover"

        analysis_content = {
            "position": position,
            # Divergence is intentionally NOT calculated here.
            "divergences": [], 
            "crossover_signal": crossover_signal
        }

        values_content = {
            "rsi": round(last_rsi, 2),
            "rsi_prev": round(prev_rsi, 2), # ✅ NEW: Provide previous value for strategies
            "signal_line": round(last_signal, 2)
        }
        
        # ✅ افزودن قرارداد صریح: اندیکاتور نام ستون اصلی خود را گزارش می‌دهد
        analysis_content['_meta'] = {'main_col': self.rsi_col}
            
        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "values": values_content,
            "analysis": analysis_content
        }
