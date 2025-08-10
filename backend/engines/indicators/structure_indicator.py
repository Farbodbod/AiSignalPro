import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Optional

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class StructureIndicator(BaseIndicator):
    """
    Market Structure Analyzer - Definitive, MTF & World-Class Version (v3.0 - No Internal Deps)
    -----------------------------------------------------------------------------------------
    This indicator acts as a pure analysis layer on top of the ZigZag indicator.
    It identifies key support/resistance levels and provides a comprehensive
    analysis of the price's position within the market structure, fully supporting
    the AiSignalPro architecture.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.zigzag_deviation = float(self.params.get('zigzag_deviation', 3.0))
        self.timeframe = self.params.get('timeframe', None)
        self.num_key_levels = int(self.params.get('num_key_levels', 5))

    def calculate(self) -> 'StructureIndicator':
        """
        ✨ FINAL ARCHITECTURE: This indicator is a pure analyzer.
        It does not calculate any new columns itself. It relies on columns
        pre-calculated by the IndicatorAnalyzer.
        """
        return self

    def analyze(self) -> Dict[str, Any]:
        """
        Performs a full, on-the-fly market structure analysis based on the latest
        pre-calculated ZigZag pivots.
        """
        # --- 1. Construct required column names and validate their existence ---
        tf_suffix = f'_{self.timeframe}' if self.timeframe else ''
        pivot_col = f'zigzag_pivots_{self.zigzag_deviation}{tf_suffix}'
        price_col = f'zigzag_prices_{self.zigzag_deviation}{tf_suffix}'

        if not all(col in self.df.columns for col in [pivot_col, price_col]):
            logger.warning(f"[{self.__class__.__name__}] Missing ZigZag columns for analysis on timeframe {self.timeframe}.")
            return {"status": "Error: Missing Dependency Columns"}

        if len(self.df) < 2: return {"status": "Insufficient Data"}
        
        # --- 2. Extract Pivots and Price Data (Bias-Free) ---
        last_closed_candle = self.df.iloc[-2]
        current_price = last_closed_candle['close']
        
        valid_df = self.df.dropna(subset=[pivot_col, price_col])
        pivots_df = valid_df[valid_df[pivot_col] != 0]

        if len(pivots_df) < 2:
            return {"status": "Awaiting Pivots"}

        # --- 3. Identify and Sort Key S/R Levels ---
        supports = sorted(pivots_df[pivots_df[pivot_col] == -1][price_col].drop_duplicates().tolist(), reverse=True)
        resistances = sorted(pivots_df[pivots_df[pivot_col] == 1][price_col].drop_duplicates().tolist(), reverse=True)
        
        key_supports = [round(s, 5) for s in supports[:self.num_key_levels]]
        key_resistances = [round(r, 5) for r in resistances[:self.num_key_levels]]
        
        # --- 4. Deep Analysis: Last Pivot & Proximity ---
        last_pivot = pivots_df.iloc[-1]
        last_pivot_type = "Support" if last_pivot[pivot_col] == -1 else "Resistance"
        
        nearest_support = next((s for s in supports if s < current_price), None)
        # For nearest resistance, we need to iterate through the descending list and find the first one greater than price
        nearest_resistance = next((r for r in reversed(resistances) if r > current_price), None)

        dist_to_support = abs(current_price - nearest_support) if nearest_support is not None else None
        dist_to_resistance = abs(nearest_resistance - current_price) if nearest_resistance is not None else None
        
        position = "In Range"
        if nearest_support is None and nearest_resistance is not None: position = "Below All Key Support"
        elif nearest_resistance is None and nearest_support is not None: position = "Above All Key Resistance"
        elif dist_to_support is not None and dist_to_resistance is not None:
             if dist_to_support < dist_to_resistance: position = "Closer to Support"
             else: position = "Closer to Resistance"

        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "analysis": {
                "current_price": round(current_price, 5),
                "position": position,
                "last_pivot": {
                    "type": last_pivot_type,
                    "price": round(last_pivot[price_col], 5),
                    "time": last_pivot.name.strftime('%Y-%m-%d %H:%M:%S')
                },
                "proximity": {
                    "nearest_support": nearest_support,
                    "nearest_resistance": nearest_resistance,
                    "distance_to_support_pct": round((dist_to_support / current_price) * 100, 2) if dist_to_support else None,
                    "distance_to_resistance_pct": round((dist_to_resistance / current_price) * 100, 2) if dist_to_resistance else None
                }
            },
            "key_levels": {
                "supports": key_supports,
                "resistances": key_resistances
            }
        }
