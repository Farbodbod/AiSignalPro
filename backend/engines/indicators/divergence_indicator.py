# backend/engines/indicators/divergence_indicator.py (v6.1 - The Hotfix Edition)
import pandas as pd
import logging
from typing import Dict, Any, Optional

from .base import BaseIndicator
from .utils import get_indicator_config_key

logger = logging.getLogger(__name__)

class DivergenceIndicator(BaseIndicator):
    """
    Divergence Engine - (v6.1 - The Hotfix Edition)
    -----------------------------------------------------------------------------------
    This version contains a critical hotfix for the fatal AttributeError caused by
    referencing a non-existent 'self.name' attribute. It now generates a robust
    unique key for aliased column naming. The output structure has also been
    hardened to be fully Sentinel-compliant.
    """
    dependencies: list = ['rsi', 'zigzag']

    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], **kwargs):
        super().__init__(df, params=params, **kwargs)
        self.timeframe = self.params.get('timeframe')
        self.lookback_pivots = int(self.params.get('lookback_pivots', 5))
        self.min_bar_distance = int(self.params.get('min_bar_distance', 5))
        
        # ✅ CRITICAL HOTFIX: Generate a stable unique key from params, as 'self.name' does not exist on indicators.
        self.unique_key = get_indicator_config_key(self.__class__.__name__.lower(), self.params)

        self.rsi_col: Optional[str] = None
        self.pivots_col: Optional[str] = None
        self.prices_col: Optional[str] = None

    def calculate(self) -> 'DivergenceIndicator':
        my_deps_config = self.params.get("dependencies", {})
        rsi_order_params = my_deps_config.get('rsi')
        zigzag_order_params = my_deps_config.get('zigzag')

        if not rsi_order_params or not zigzag_order_params:
            logger.error(f"[{self.unique_key}] on {self.timeframe}: RSI or ZigZag dependency not defined.")
            return self
        
        rsi_unique_key = get_indicator_config_key('rsi', rsi_order_params)
        zigzag_unique_key = get_indicator_config_key('zigzag', zigzag_order_params)
        
        rsi_instance = self.dependencies.get(rsi_unique_key)
        zigzag_instance = self.dependencies.get(zigzag_unique_key)
        
        if not isinstance(rsi_instance, BaseIndicator) or not isinstance(zigzag_instance, BaseIndicator):
            logger.warning(f"[{self.unique_key}] on {self.timeframe}: missing critical dependencies.")
            return self

        # Dynamically find the correct column names from dependencies
        self.rsi_col = next((col for col in rsi_instance.df.columns if col.startswith('RSI_')), None)
        self.pivots_col = getattr(zigzag_instance, 'pivots_col', None)
        self.prices_col = getattr(zigzag_instance, 'prices_col', None)

        if not all([self.rsi_col, self.pivots_col, self.prices_col]):
            logger.warning(f"[{self.unique_key}] on {self.timeframe}: could not find required columns in dependencies.")
            return self
        
        # Join dependency data using unique names to prevent conflicts
        rsi_col_aliased = f"RSI_for_{self.unique_key}"
        pivots_col_aliased = f"PIVOTS_for_{self.unique_key}"
        prices_col_aliased = f"PRICES_for_{self.unique_key}"
        
        self.df[rsi_col_aliased] = rsi_instance.df[self.rsi_col]
        self.df[pivots_col_aliased] = zigzag_instance.df[self.pivots_col]
        self.df[prices_col_aliased] = zigzag_instance.df[self.prices_col]
        
        # Update internal column names to the aliased versions
        self.rsi_col, self.pivots_col, self.prices_col = rsi_col_aliased, pivots_col_aliased, prices_col_aliased

        return self

    def analyze(self) -> Dict[str, Any]:
        empty_analysis = {"signals": []}
        required_cols = [self.rsi_col, self.pivots_col, self.prices_col]
        if not all(col in self.df.columns for col in required_cols):
            return {"status": "Calculation Incomplete", "values": empty_analysis, "analysis": empty_analysis}

        valid_df = self.df.dropna(subset=required_cols)
        pivots_df = valid_df[valid_df[self.pivots_col] != 0]

        if len(pivots_df) < 2:
            # ✅ SENTINEL COMPLIANCE FIX: Ensure a full, valid object is always returned.
            return {"status": "OK", "timeframe": self.timeframe or 'Base', "values": empty_analysis, "analysis": empty_analysis}
            
        signals = []
        recent_pivots = pivots_df.tail(self.lookback_pivots)
        for i in range(len(recent_pivots)):
            for j in range(i + 1, len(recent_pivots)):
                pivot1 = recent_pivots.iloc[i]
                pivot2 = recent_pivots.iloc[j]

                bar_distance = self.df.index.get_loc(pivot2.name) - self.df.index.get_loc(pivot1.name)
                if bar_distance < self.min_bar_distance: continue

                price1, rsi1 = pivot1[self.prices_col], pivot1[self.rsi_col]
                price2, rsi2 = pivot2[self.prices_col], pivot2[self.rsi_col]
                
                divergence = None
                if pivot1[self.pivots_col] == 1 and pivot2[self.pivots_col] == 1: # Two peaks
                    if price2 > price1 and rsi2 < rsi1: divergence = {"type": "Regular Bearish"}
                    if price2 < price1 and rsi2 > rsi1: divergence = {"type": "Hidden Bearish"}
                elif pivot1[self.pivots_col] == -1 and pivot2[self.pivots_col] == -1: # Two troughs
                    if price2 < price1 and rsi2 > rsi1: divergence = {"type": "Regular Bullish"}
                    if price2 > price1 and rsi2 < rsi1: divergence = {"type": "Hidden Bullish"}

                if divergence:
                    signals.append({
                        **divergence,
                        "pivots": [
                            {"time": pivot1.name.strftime('%Y-%m-%d %H:%M:%S'), "price": round(price1, 5), "oscillator_value": round(rsi1, 2)},
                            {"time": pivot2.name.strftime('%Y-%m-%d %H:%M:%S'), "price": round(price2, 5), "oscillator_value": round(rsi2, 2)}
                        ]
                    })
        
        analysis_content = {"signals": signals}
        return {"status": "OK", "timeframe": self.timeframe or 'Base', "values": analysis_content, "analysis": analysis_content}
