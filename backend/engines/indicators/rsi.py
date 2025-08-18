# backend/engines/indicators/rsi.py
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, List

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class RsiIndicator(BaseIndicator):
    """
    RSI Indicator - (v7.0 - DI Native & Cleaned Architecture)
    -------------------------------------------------------------------------------------
    This world-class version is re-engineered to natively support the Dependency
    Injection (DI) architecture. The obsolete static methods (`get_col_name`) have 
    been removed. The optional divergence detection feature now robustly consumes
    the ZigZag instance. The core RSI calculation and analysis logic remain 100% intact.
    """
    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], dependencies: Dict[str, BaseIndicator], **kwargs):
        super().__init__(df, params=params, dependencies=dependencies, **kwargs)
        self.period = int(self.params.get('period', 14))
        self.timeframe = self.params.get('timeframe')
        self.detect_divergence = bool(self.params.get('detect_divergence', True))
        self.divergence_lookback = int(self.params.get('divergence_lookback', 5))
        
        # Simplified, robust, and locally-scoped column names
        self.rsi_col = f'RSI_{self.period}'
        self.signal_col = f'RSI_signal_{self.period}'

    def calculate(self) -> 'RsiIndicator':
        """
        Calculates the RSI value using the standard Wilder's smoothing method.
        The core mathematical logic is 100% preserved.
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

        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        
        self.df[self.rsi_col] = rsi
        # Optional: Calculate a signal line for RSI
        self.df[self.signal_col] = rsi.ewm(span=9, adjust=False).mean()

        return self

    def _find_divergences(self, rsi_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Finds divergences by consuming the injected ZigZag instance. This logic is
        now harmonized with other oscillators like MFI and Stochastic.
        """
        if not self.detect_divergence: return []

        zigzag_instance = self.dependencies.get('zigzag')
        if not zigzag_instance:
            logger.debug(f"[{self.__class__.__name__}] ZigZag dependency not provided for divergence detection on {self.timeframe}.")
            return []

        zigzag_df = zigzag_instance.df
        pivots_col_options = [col for col in zigzag_df.columns if 'PIVOTS' in col.upper()]
        prices_col_options = [col for col in zigzag_df.columns if 'PRICES' in col.upper()]

        if not pivots_col_options or not prices_col_options:
            logger.warning(f"[{self.__class__.__name__}] Could not find pivot/price columns in ZigZag data for divergence detection.")
            return []
        
        pivot_col, price_col = pivots_col_options[0], prices_col_options[0]
        
        analysis_df = rsi_df.join(zigzag_df[[pivot_col, price_col]], how='left')
        analysis_df[self.rsi_col] = analysis_df[self.rsi_col].ffill()
        
        pivots_df = analysis_df[analysis_df[pivot_col] != 0].dropna(subset=[self.rsi_col])
        if len(pivots_df) < 2: return []
        
        last_pivot = pivots_df.iloc[-1]
        previous_pivots = pivots_df.iloc[-self.divergence_lookback:-1]
        divergences = []
        for i in range(len(previous_pivots)):
            prev_pivot = previous_pivots.iloc[i]
            price1, rsi1 = prev_pivot[price_col], prev_pivot[self.rsi_col]
            price2, rsi2 = last_pivot[price_col], last_pivot[self.rsi_col]
            if prev_pivot[pivot_col] == 1 and last_pivot[pivot_col] == 1:
                if price2 > price1 and rsi2 < rsi1: divergences.append({'type': 'Regular Bearish'})
                if price2 < price1 and rsi2 > rsi1: divergences.append({'type': 'Hidden Bearish'})
            elif prev_pivot[pivot_col] == -1 and last_pivot[pivot_col] == -1:
                if price2 < price1 and rsi2 > rsi1: divergences.append({'type': 'Regular Bullish'})
                if price2 > price1 and rsi2 < rsi1: divergences.append({'type': 'Hidden Bullish'})
        return divergences

    def analyze(self) -> Dict[str, Any]:
        """ Provides analysis on RSI levels and divergences. """
        required_cols = [self.rsi_col, self.signal_col]
        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 2: return {"status": "Insufficient Data"}

        # Dynamic levels can be implemented here if needed, for now using static
        oversold, overbought = 30, 70
        last_rsi, last_signal = valid_df.iloc[-1][self.rsi_col], valid_df.iloc[-1][self.signal_col]
        
        position = "Neutral"
        if last_rsi > overbought: position = "Overbought"
        elif last_rsi < oversold: position = "Oversold"
            
        divergences = self._find_divergences(valid_df)
        
        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "values": {
                "rsi": round(last_rsi, 2),
                "signal_line": round(last_signal, 2)
            },
            "analysis": {
                "position": position,
                "divergences": divergences,
                "crossover_signals": [] # Placeholder for future crossover logic
            }
        }
