import pandas as pd
import logging
from typing import Dict, Any, List, Optional

# BaseIndicator, ZigzagIndicator, RsiIndicator را از ماژول‌های مربوطه وارد کنید
from .base import BaseIndicator
from .zigzag import ZigzagIndicator
from .rsi import RsiIndicator

logger = logging.getLogger(__name__)

class DivergenceIndicator(BaseIndicator):
    """
    Divergence Analysis Engine - Definitive World-Class Version
    -------------------------------------------------------------
    This version embodies the highest standards of the AiSignalPro project.

    Architectural Principles:
    - Correctness: Implements the correct search algorithm for finding divergences.
    - Comprehensiveness: Detects both Regular and Hidden divergences.
    - Robustness: Unit-agnostic distance filter and full data validation.
    - Insightful API: Returns a list of all detected signals, not just one.
    - Maintainability: Logic is refactored into clean, testable helper methods.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        # --- Configuration ---
        self.zigzag_deviation = self.params.get('zigzag_deviation', 3.0)
        self.rsi_period = self.params.get('rsi_period', 14)
        self.lookback_pivots = self.params.get('lookback_pivots', 5) # How many past pivots to check against
        self.min_bar_distance = self.params.get('min_bar_distance', 5) # Min bars between pivots
        self.overbought = self.params.get('overbought', 68)
        self.oversold = self.params.get('oversold', 32)
        
        self._rsi_col = f'rsi_{self.rsi_period}'
        self._pivots_col = f'zigzag_pivots_{self.zigzag_deviation}'
        self._prices_col = f'zigzag_prices_{self.zigzag_deviation}'
        
    def calculate(self) -> 'DivergenceIndicator':
        """Ensures the underlying indicators (RSI, ZigZag) are calculated."""
        # This method prepares dependencies. In a real pipeline, this might be
        # handled by an orchestrator, but for encapsulation, we ensure it here.
        if self._rsi_col not in self.df.columns:
            logger.info(f"Calculating dependency: {self._rsi_col}")
            self.df = RsiIndicator(self.df, params={'period': self.rsi_period}).calculate()
        
        if self._pivots_col not in self.df.columns:
            logger.info(f"Calculating dependency: {self._pivots_col}")
            self.df = ZigzagIndicator(self.df, params={'deviation': self.zigzag_deviation}).calculate()
            
        return self

    def _check_divergence_pair(self, pivot1: pd.Series, pivot2: pd.Series) -> Optional[Dict[str, Any]]:
        """Checks a single pair of pivots for any type of divergence."""
        price1, rsi1 = pivot1[self.prices_col], self.df.loc[pivot1.name, self._rsi_col]
        price2, rsi2 = pivot2[self.prices_col], self.df.loc[pivot2.name, self._rsi_col]

        # Bearish checks (comparing two peaks)
        if pivot1[self._pivots_col] == 1 and pivot2[self._pivots_col] == 1:
            # Regular Bearish: Higher High in Price, Lower High in RSI
            if price2 > price1 and rsi2 < rsi1:
                return {"type": "Regular Bearish", "strength": "Strong" if rsi2 > self.overbought else "Normal"}
            # Hidden Bearish: Lower High in Price, Higher High in RSI
            if price2 < price1 and rsi2 > rsi1:
                return {"type": "Hidden Bearish", "strength": "Continuation Signal"}

        # Bullish checks (comparing two troughs)
        elif pivot1[self._pivots_col] == -1 and pivot2[self._pivots_col] == -1:
            # Regular Bullish: Lower Low in Price, Higher Low in RSI
            if price2 < price1 and rsi2 > rsi1:
                return {"type": "Regular Bullish", "strength": "Strong" if rsi2 < self.oversold else "Normal"}
            # Hidden Bullish: Higher Low in Price, Lower Low in RSI
            if price2 > price1 and rsi2 < rsi1:
                return {"type": "Hidden Bullish", "strength": "Continuation Signal"}
        
        return None

    def analyze(self) -> Dict[str, Any]:
        """Analyzes the dataframe for all valid divergences within the lookback window."""
        self.calculate() # Ensure data is ready
        
        if any(col not in self.df.columns for col in [self._pivots_col, self._prices_col, self._rsi_col]):
            logger.error("Required columns for divergence analysis are missing.")
            return {"status": "Error: Missing Dependency Columns", "signals": []}

        # Get all confirmed pivots
        pivots_df = self.df[self.df[self._pivots_col] != 0].copy()
        
        if len(pivots_df) < 2:
            return {"status": "OK", "signals": []}

        # ✨ FIX: Correct search logic - Compare the latest pivot with previous ones
        last_pivot = pivots_df.iloc[-1]
        # Look at previous pivots within the lookback window
        previous_pivots = pivots_df.iloc[-self.lookback_pivots:-1]

        signals = []
        for i in range(len(previous_pivots)):
            prev_pivot = previous_pivots.iloc[i]
            
            # ✨ FIX: Robust bar distance check
            bar_distance = self.df.index.get_loc(last_pivot.name) - self.df.index.get_loc(prev_pivot.name)
            if bar_distance < self.min_bar_distance:
                continue

            divergence = self._check_divergence_pair(prev_pivot, last_pivot)
            if divergence:
                signal_data = {
                    **divergence,
                    "pivots": [
                        {"time": prev_pivot.name.strftime('%Y-%m-%d %H:%M:%S'), "price": round(prev_pivot[self.prices_col], 5), "rsi": round(self.df.loc[prev_pivot.name, self._rsi_col], 2)},
                        {"time": last_pivot.name.strftime('%Y-%m-%d %H:%M:%S'), "price": round(last_pivot[self.prices_col], 5), "rsi": round(self.df.loc[last_pivot.name, self._rsi_col], 2)}
                    ]
                }
                signals.append(signal_data)

        # ✨ IMPROVEMENT: Return all found signals
        return {"status": "OK", "signals": signals}
