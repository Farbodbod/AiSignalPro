# backend/engines/indicators/divergence_indicator.py
import pandas as pd
import logging
import json
from typing import Dict, Any

from .base import BaseIndicator
from .utils import get_indicator_config_key # ✅ World-Class Practice: Import from shared utils

logger = logging.getLogger(__name__)

class DivergenceIndicator(BaseIndicator):
    """
    Divergence Engine - (v5.1 - Definitive Dependency Hotfix)
    -----------------------------------------------------------------------------------
    This version contains the definitive, world-class fix for dependency lookup.
    It now correctly reconstructs the unique_keys of its dependencies (RSI, ZigZag)
    from its own configuration, ensuring a flawless and robust connection.
    """
    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], dependencies: Dict[str, BaseIndicator], **kwargs):
        super().__init__(df, params=params, dependencies=dependencies, **kwargs)
        self.timeframe = self.params.get('timeframe')
        self.lookback_pivots = int(self.params.get('lookback_pivots', 5))
        self.min_bar_distance = int(self.params.get('min_bar_distance', 5))
        self.rsi_col: str | None = None
        self.pivots_col: str | None = None
        self.prices_col: str | None = None

    def calculate(self) -> 'DivergenceIndicator':
        """
        Prepares the DataFrame by correctly looking up and joining data from its
        RSI and ZigZag dependencies.
        """
        # ✅ DEFINITIVE FIX: The correct way to look up dependencies.
        my_deps_config = self.params.get("dependencies", {})
        rsi_order_params = my_deps_config.get('rsi')
        zigzag_order_params = my_deps_config.get('zigzag')

        if not rsi_order_params or not zigzag_order_params:
            logger.error(f"[{self.__class__.__name__}] on {self.timeframe} cannot run: RSI or ZigZag dependency not defined in config.")
            return self
        
        rsi_unique_key = get_indicator_config_key('rsi', rsi_order_params)
        zigzag_unique_key = get_indicator_config_key('zigzag', zigzag_order_params)
        
        rsi_instance = self.dependencies.get(rsi_unique_key)
        zigzag_instance = self.dependencies.get(zigzag_unique_key)
        
        if not isinstance(rsi_instance, BaseIndicator) or not isinstance(zigzag_instance, BaseIndicator):
            logger.warning(f"[{self.__class__.__name__}] on {self.timeframe} missing critical dependencies (RSI or ZigZag). Skipping calculation.")
            return self

        rsi_df, zigzag_df = rsi_instance.df, zigzag_instance.df
        rsi_col_options = [col for col in rsi_df.columns if 'RSI' in col.upper()]
        pivots_col_options = [col for col in zigzag_df.columns if 'PIVOTS' in col.upper()]
        prices_col_options = [col for col in zigzag_df.columns if 'PRICES' in col.upper()]

        if not all([rsi_col_options, pivots_col_options, prices_col_options]):
            logger.warning(f"[{self.__class__.__name__}] on {self.timeframe} could not find required columns in dependency dataframes.")
            return self
            
        self.rsi_col, self.pivots_col, self.prices_col = rsi_col_options[0], pivots_col_options[0], prices_col_options[0]

        self.df = self.df.join(rsi_df[[self.rsi_col]], how='left')
        self.df = self.df.join(zigzag_df[[self.pivots_col, self.prices_col]], how='left')
        return self

    def analyze(self) -> Dict[str, Any]:
        """ Analyzes the prepared DataFrame for divergences. """
        required_cols = [self.rsi_col, self.pivots_col, self.prices_col]
        if not all(col in self.df.columns for col in required_cols):
            return {"status": "Calculation Incomplete - Required columns missing"}

        valid_df = self.df.dropna(subset=required_cols)
        pivots_df = valid_df[valid_df[self.pivots_col] != 0]

        if len(pivots_df) < 2: return {"status": "OK", "signals": []}
            
        last_pivot, previous_pivots, signals = pivots_df.iloc[-1], pivots_df.iloc[-self.lookback_pivots:-1], []
        for i in range(len(previous_pivots)):
            prev_pivot = previous_pivots.iloc[i]
            if last_pivot.name not in self.df.index or prev_pivot.name not in self.df.index: continue
            bar_distance = self.df.index.get_loc(last_pivot.name) - self.df.index.get_loc(prev_pivot.name)
            if bar_distance < self.min_bar_distance: continue
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
                signals.append({**divergence, "pivots": [{"time": prev_pivot.name.strftime('%Y-%m-%d %H:%M:%S'), "price": round(price1, 5), "oscillator_value": round(rsi1, 2)}, {"time": last_pivot.name.strftime('%Y-%m-%d %H:%M:%S'), "price": round(price2, 5), "oscillator_value": round(rsi2, 2)}]})
        return {"status": "OK", "signals": signals, "timeframe": self.timeframe or 'Base'}
