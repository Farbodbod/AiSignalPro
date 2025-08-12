import pandas as pd
import logging
from typing import Dict, Any, List, Optional

from .base import BaseIndicator
from .zigzag import ZigzagIndicator # For standardized column naming
from .rsi import RsiIndicator # For standardized column naming

logger = logging.getLogger(__name__)

class DivergenceIndicator(BaseIndicator):
    """
    Divergence Engine - (v4.0 - Multi-Version Aware)
    -----------------------------------------------------------------------------------
    This version is fully compatible with the IndicatorAnalyzer v9.0's Multi-Version
    Engine. It intelligently reads its dependency configurations for both RSI and
    ZigZag to request and use the specific versions it needs.
    """
    # ✅ MIRACLE UPGRADE: Dependencies are now declared in config.
    dependencies: list = []

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.timeframe = self.params.get('timeframe', None)
        self.lookback_pivots = int(self.params.get('lookback_pivots', 5))
        self.min_bar_distance = int(self.params.get('min_bar_distance', 5))

        # ✅ MIRACLE UPGRADE: The indicator now reads its specific dependency configs.
        dep_configs = self.params.get('dependencies', {})
        self.zigzag_dependency_params = dep_configs.get('zigzag', {'deviation': 3.0})
        self.rsi_dependency_params = dep_configs.get('rsi', {'period': 14})

    def calculate(self) -> 'DivergenceIndicator':
        """ This is a pure analyzer; it relies on pre-calculated columns. """
        return self

    def analyze(self) -> Dict[str, Any]:
        """ Analyzes the pre-calculated RSI and ZigZag data for divergences. """
        # ✅ MIRACLE UPGRADE: Dynamically construct the required column names via contracts.
        rsi_col = RsiIndicator.get_col_name(self.rsi_dependency_params, self.timeframe)
        pivots_col = ZigzagIndicator.get_pivots_col_name(self.zigzag_dependency_params, self.timeframe)
        prices_col = ZigzagIndicator.get_prices_col_name(self.zigzag_dependency_params, self.timeframe)

        required_cols = [rsi_col, pivots_col, prices_col]
        if any(col not in self.df.columns for col in required_cols):
            logger.warning(f"[{self.__class__.__name__}] Missing one or more required columns on {self.timeframe}. Required: {required_cols}")
            return {"status": "Error: Missing Dependency Columns"}

        valid_df = self.df.dropna(subset=required_cols)
        pivots_df = valid_df[valid_df[pivots_col] != 0]

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

