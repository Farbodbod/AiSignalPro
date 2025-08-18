# backend/engines/indicators/divergence_indicator.py
import pandas as pd
import logging
from typing import Dict, Any

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class DivergenceIndicator(BaseIndicator):
    """
    Divergence Engine - (v5.0 - Dependency Injection Native)
    -----------------------------------------------------------------------------------
    This version is rewritten to natively support the Dependency Injection architecture.
    It no longer relies on static methods or 'guessing' column names. Instead, it
    directly consumes the instances of its dependencies (RSI, ZigZag) passed to it
    by the modern IndicatorAnalyzer, making it robust and decoupled.
    """
    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], dependencies: Dict[str, BaseIndicator], **kwargs):
        super().__init__(df, params=params, dependencies=dependencies, **kwargs)
        self.timeframe = self.params.get('timeframe')
        self.lookback_pivots = int(self.params.get('lookback_pivots', 5))
        self.min_bar_distance = int(self.params.get('min_bar_distance', 5))

        # These will store the actual column names after they are found in calculate()
        self.rsi_col: str | None = None
        self.pivots_col: str | None = None
        self.prices_col: str | None = None

    def calculate(self) -> 'DivergenceIndicator':
        """
        Calculates divergence by consuming dependency data from RSI and ZigZag instances.
        This method prepares the DataFrame for the analyze() method.
        """
        # 1. Directly receive dependency instances injected by the Analyzer
        rsi_instance = self.dependencies.get('rsi')
        zigzag_instance = self.dependencies.get('zigzag')

        if not rsi_instance or not zigzag_instance:
            logger.warning(f"[{self.__class__.__name__}] on {self.timeframe} missing critical dependencies (RSI or ZigZag). Skipping calculation.")
            return self

        # 2. Get the DataFrames from the dependencies
        rsi_df = rsi_instance.df
        zigzag_df = zigzag_instance.df
        
        # 3. Intelligently find the required columns from the dependency DataFrames
        rsi_col_options = [col for col in rsi_df.columns if 'RSI' in col.upper()]
        pivots_col_options = [col for col in zigzag_df.columns if 'PIVOTS' in col.upper()]
        prices_col_options = [col for col in zigzag_df.columns if 'PRICES' in col.upper()]

        if not rsi_col_options or not pivots_col_options or not prices_col_options:
            logger.warning(f"[{self.__class__.__name__}] on {self.timeframe} could not find required columns in dependency dataframes.")
            return self
            
        self.rsi_col = rsi_col_options[0]
        self.pivots_col = pivots_col_options[0]
        self.prices_col = prices_col_options[0]

        # 4. Join the necessary columns into this indicator's main DataFrame
        self.df = self.df.join(rsi_df[[self.rsi_col]], how='left')
        self.df = self.df.join(zigzag_df[[self.pivots_col, self.prices_col]], how='left')
        
        return self

    def analyze(self) -> Dict[str, Any]:
        """ Analyzes the prepared DataFrame for divergences. """
        required_cols = [self.rsi_col, self.pivots_col, self.prices_col]
        
        if any(col is None for col in required_cols) or any(col not in self.df.columns for col in required_cols):
            logger.warning(f"[{self.__class__.__name__}] Missing required data columns for analysis on {self.timeframe}.")
            return {"status": "Error: Missing Data for Analysis"}

        valid_df = self.df.dropna(subset=required_cols)
        pivots_df = valid_df[valid_df[self.pivots_col] != 0]

        if len(pivots_df) < 2:
            return {"status": "OK", "signals": []}
            
        last_pivot = pivots_df.iloc[-1]
        previous_pivots = pivots_df.iloc[-self.lookback_pivots:-1]
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
            
            if prev_pivot[self.pivots_col] == 1 and last_pivot[self.pivots_col] == 1: # Two peaks
                if price2 > price1 and rsi2 < rsi1: divergence = {"type": "Regular Bearish"}
                if price2 < price1 and rsi2 > rsi1: divergence = {"type": "Hidden Bearish"}
            elif prev_pivot[self.pivots_col] == -1 and last_pivot[self.pivots_col] == -1: # Two troughs
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
