import pandas as pd
import logging
from typing import Dict, Any, List, Optional
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class DivergenceIndicator(BaseIndicator):
    """
    Divergence Engine - Definitive, MTF & World-Class Version (v3.0 - No Internal Deps)
    -----------------------------------------------------------------------------------
    This version adheres to the final AiSignalPro architecture. It acts as a pure
    analysis engine, consuming pre-calculated RSI and ZigZag columns provided by the
    IndicatorAnalyzer. This eliminates redundant calculations and makes the system
    more robust and efficient.
    """
    dependencies = ['rsi', 'zigzag']

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.timeframe = self.params.get('timeframe', None)
        self.zigzag_deviation = float(self.params.get('zigzag_deviation', 3.0))
        self.rsi_period = int(self.params.get('rsi_period', 14))
        self.lookback_pivots = int(self.params.get('lookback_pivots', 5))
        self.min_bar_distance = int(self.params.get('min_bar_distance', 5))

    def calculate(self) -> 'DivergenceIndicator':
        """
        ✨ FINAL ARCHITECTURE: This indicator is a pure analyzer.
        It does not calculate any new columns itself. It relies on columns
        pre-calculated by the IndicatorAnalyzer. The `calculate` method
        is now a simple pass-through.
        """
        # All required data (RSI, Zigzag) is expected to be on self.df already.
        # This method's only job is to return the instance.
        return self

    def analyze(self) -> Dict[str, Any]:
        """
        Analyzes the pre-calculated RSI and ZigZag data for divergences.
        """
        # ✨ THE MIRACLE FIX: Dynamically construct the required column names
        # This creates a robust "contract" with the IndicatorAnalyzer.
        tf_suffix = f'_{self.timeframe}' if self.timeframe else ''
        
        rsi_col = f'rsi_{self.rsi_period}{tf_suffix}'
        pivots_col = f'zigzag_pivots_{self.zigzag_deviation}{tf_suffix}'
        prices_col = f'zigzag_prices_{self.zigzag_deviation}{tf_suffix}'

        required_cols = [rsi_col, pivots_col, prices_col]
        if any(col not in self.df.columns for col in required_cols):
            logger.warning(f"[{self.__class__.__name__}] Missing one or more required columns for analysis on timeframe {self.timeframe}. Required: {required_cols}")
            return {"status": "Error: Missing Dependency Columns", "signals": []}

        # The core divergence finding logic remains unchanged, as it was already powerful.
        valid_df = self.df.dropna(subset=required_cols)
        pivots_df = valid_df[valid_df[pivots_col] != 0]

        if len(pivots_df) < 2:
            return {"status": "OK", "signals": []}
            
        last_pivot = pivots_df.iloc[-1]
        previous_pivots = pivots_df.iloc[-self.lookback_pivots:-1]
        signals = []

        for i in range(len(previous_pivots)):
            prev_pivot = previous_pivots.iloc[i]
            
            # Ensure index is valid before using .get_loc
            if last_pivot.name not in self.df.index or prev_pivot.name not in self.df.index:
                continue

            bar_distance = self.df.index.get_loc(last_pivot.name) - self.df.index.get_loc(prev_pivot.name)
            if bar_distance < self.min_bar_distance:
                continue

            price1, rsi1 = prev_pivot[prices_col], self.df.loc[prev_pivot.name, rsi_col]
            price2, rsi2 = last_pivot[prices_col], self.df.loc[last_pivot.name, rsi_col]
            divergence = None
            
            if prev_pivot[pivots_col] == 1 and last_pivot[pivots_col] == 1: # Two peaks
                if price2 > price1 and rsi2 < rsi1: divergence = {"type": "Regular Bearish"}
                if price2 < price1 and rsi2 > rsi1: divergence = {"type": "Hidden Bearish"}
            elif prev_pivot[pivots_col] == -1 and last_pivot[pivots_col] == -1: # Two troughs
                if price2 < price1 and rsi2 > rsi1: divergence = {"type": "Regular Bullish"}
                if price2 > price1 and rsi2 < rsi1: divergence = {"type": "Hidden Bullish"}
            
            if divergence:
                signals.append({
                    **divergence,
                    "pivots": [
                        {"time": prev_pivot.name.strftime('%Y-%m-%d %H:%M:%S'), "price": round(price1, 5), "oscillator_value": round(rsi1, 2)},
                        {"time": last_pivot.name.strftime('%Y-%m-%d %H:%M:%S'), "price": round(price2, 5), "oscillator_value": round(rsi2, 2)}
                    ]
                })
                
        return {"status": "OK", "signals": signals, "timeframe": self.timeframe or 'Base'}
