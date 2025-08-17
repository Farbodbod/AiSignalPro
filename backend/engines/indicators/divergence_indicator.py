# backend/engines/indicators/divergence_indicator.py (v6.0 - Final Refactor)

import pandas as pd
import logging
from typing import Dict, Any, List, Optional

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class DivergenceIndicator(BaseIndicator):
    """
    Divergence Engine - (v6.0 - Logical Refactor)
    -----------------------------------------------------------------------------------
    This version is refactored to be a true analysis engine. It no longer joins DataFrames
    and instead relies on the parent `IndicatorAnalyzer` to provide a complete DataFrame
    with all dependencies' data already present.
    """
    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], dependencies: Dict[str, BaseIndicator], **kwargs):
        super().__init__(df, params=params, dependencies=dependencies, **kwargs)
        self.timeframe = self.params.get('timeframe')
        self.lookback_pivots = int(self.params.get('lookback_pivots', 5))
        self.min_bar_distance = int(self.params.get('min_bar_distance', 5))

        self.rsi_col: Optional[str] = None
        self.pivots_col: Optional[str] = None
        self.prices_col: Optional[str] = None

    def calculate(self) -> 'DivergenceIndicator':
        """
        No calculation is performed here. This indicator is purely for analysis,
        and it expects the `df` to be pre-populated by the `IndicatorAnalyzer`.
        """
        rsi_instance = self.dependencies.get('rsi')
        zigzag_instance = self.dependencies.get('zigzag')

        if not isinstance(rsi_instance, BaseIndicator) or not isinstance(zigzag_instance, BaseIndicator):
            logger.warning(f"[{self.__class__.__name__}] on {self.timeframe} missing critical dependencies (RSI or ZigZag). Skipping calculation.")
            return self

        rsi_df = rsi_instance.df
        zigzag_df = zigzag_instance.df
        
        rsi_col_options = [col for col in rsi_df.columns if 'rsi_' in col.lower()]
        pivots_col_options = [col for col in zigzag_df.columns if 'pivots' in col.lower()]
        prices_col_options = [col for col in zigzag_df.columns if 'prices' in col.lower()]

        if not rsi_col_options or not pivots_col_options or not prices_col_options:
            logger.warning(f"[{self.__class__.__name__}] on {self.timeframe} could not find required columns in dependency dataframes. This may indicate a prior failure.")
            return self
            
        self.rsi_col = rsi_col_options[0]
        self.pivots_col = pivots_col_options[0]
        self.prices_col = prices_col_options[0]
        
        # ✅ FIX: Don't join DataFrames here. Rely on the IndicatorAnalyzer to have already
        # merged the data into the main `self.df`
        return self

    def analyze(self) -> Dict[str, Any]:
        required_cols = [self.rsi_col, self.pivots_col, self.prices_col]
        
        if any(col is None for col in required_cols) or any(col not in self.df.columns for col in required_cols):
            logger.warning(f"[{self.__class__.__name__}] Missing required data columns for analysis on {self.timeframe}.")
            return {"status": "Error: Missing Data for Analysis"}

        valid_df = self.df.dropna(subset=required_cols)
        pivots_df = valid_df[valid_df[self.pivots_col] != 0]

        if len(pivots_df) < 2:
            return {"status": "OK", "signals": []}
            
        last_pivot = pivots_df.iloc[-1]
        previous_pivots = pivots_df.iloc[-self.lookback_pivots-1:-1] # Added -1 to avoid counting last pivot
        signals = []

        for i in range(len(previous_pivots)):
            prev_pivot = previous_pivots.iloc[i]
            
            if last_pivot.name not in self.df.index or prev_pivot.name not in self.df.index:
                continue

            bar_distance = self.df.index.get_loc(last_pivot.name) - self.df.index.get_loc(prev_pivot.name)
            if bar_distance < self.min_bar_distance:
                continue

            price1, rsi1 = prev_pivot[self.prices_col], self.df.loc[prev_pivot.name, self.rsi_col]
            price2, rsi2 = last_pivot[self.prices_col], self.df.loc[last_pivot.name, self.rsi_col]
            divergence = None
            
            # ✅ FIX: Use both prices and RSI values for divergence check.
            is_bullish = prev_pivot[self.pivots_col] == -1 and last_pivot[self.pivots_col] == -1
            is_bearish = prev_pivot[self.pivots_col] == 1 and last_pivot[self.pivots_col] == 1
            
            if is_bearish:
                # Regular Bearish: price higher high, RSI lower high
                if price2 > price1 and rsi2 < rsi1: divergence = {"type": "Regular Bearish"}
                # Hidden Bearish: price lower high, RSI higher high
                if price2 < price1 and rsi2 > rsi1: divergence = {"type": "Hidden Bearish"}
            elif is_bullish:
                # Regular Bullish: price lower low, RSI higher low
                if price2 < price1 and rsi2 > rsi1: divergence = {"type": "Regular Bullish"}
                # Hidden Bullish: price higher low, RSI lower low
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
