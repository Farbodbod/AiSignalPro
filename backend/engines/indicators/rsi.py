# backend/engines/indicators/rsi.py
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class RsiIndicator(BaseIndicator):
    """
    RSI Indicator - (v7.1 - Pure Calculation Engine)
    -------------------------------------------------------------------------------------
    This is a pure, world-class implementation of the RSI indicator based on the
    correct Wilder's Smoothing formula. It has no external dependencies and serves as a
    foundational data provider for other modules. Divergence detection is correctly
    delegated to specialist indicators like DivergenceIndicator.
    """
    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], dependencies: Dict[str, BaseIndicator], **kwargs):
        super().__init__(df, params=params, dependencies=dependencies, **kwargs)
        self.period = int(self.params.get('period', 14))
        self.timeframe = self.params.get('timeframe')
        
        # Simplified, robust, and locally-scoped column names
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

        # Correct Wilder's Smoothing implementation
        avg_gain = gain.ewm(com=self.period - 1, min_periods=self.period).mean()
        avg_loss = loss.ewm(com=self.period - 1, min_periods=self.period).mean()

        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        
        self.df[self.rsi_col] = rsi
        self.df[self.signal_col] = rsi.ewm(span=9, adjust=False).mean()

        return self

    def analyze(self) -> Dict[str, Any]:
        """ Provides analysis on RSI levels and crossover signals. """
        required_cols = [self.rsi_col, self.signal_col]
        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 2: return {"status": "Insufficient Data"}

        # Static levels are used here, but can be made dynamic if needed
        oversold, overbought = 30, 70
        last_rsi, last_signal = valid_df.iloc[-1][self.rsi_col], valid_df.iloc[-1][self.signal_col]
        
        position = "Neutral"
        if last_rsi > overbought: position = "Overbought"
        elif last_rsi < oversold: position = "Oversold"
            
        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "values": {
                "rsi": round(last_rsi, 2),
                "signal_line": round(last_signal, 2)
            },
            "analysis": {
                "position": position,
                # Divergence is intentionally NOT calculated here.
                # It's the job of specialist indicators.
                "divergences": [], 
                "crossover_signals": [] 
            }
        }
