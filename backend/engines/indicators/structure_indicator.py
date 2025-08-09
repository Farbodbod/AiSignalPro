import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Optional
from .base import BaseIndicator
from .zigzag import ZigzagIndicator

logger = logging.getLogger(__name__)

class StructureIndicator(BaseIndicator):
    """ Market Structure Analyzer - Definitive, MTF & World-Class Version (v2.1 - Bugfix) """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {}); self.zigzag_deviation = float(self.params.get('zigzag_deviation', 3.0))
        self.timeframe = self.params.get('timeframe', None); self.num_key_levels = int(self.params.get('num_key_levels', 5))
        self._zigzag_indicator: Optional[ZigzagIndicator] = None

    def calculate(self) -> 'StructureIndicator':
        zigzag_params = {'deviation': self.zigzag_deviation, 'timeframe': self.timeframe}
        zigzag_instance = ZigzagIndicator(self.df, params=zigzag_params).calculate()
        self.df = zigzag_instance.df
        self._zigzag_indicator = zigzag_instance
        return self

    def analyze(self) -> Dict[str, Any]:
        if self._zigzag_indicator is None: self.calculate()
        pivot_col = self._zigzag_indicator.col_pivots; price_col = self._zigzag_indicator.col_prices
        if pivot_col not in self.df.columns: return {"status": "Error: ZigZag columns not found."}
        if len(self.df) < 2: return {"status": "Insufficient Data"}
        last_closed_candle = self.df.iloc[-2]; current_price = last_closed_candle['close']
        pivots_df = self.df[self.df[pivot_col] != 0].copy()
        if len(pivots_df) < 2: return {"status": "Awaiting Pivots"}
        supports = sorted(pivots_df[pivots_df[pivot_col] == -1][price_col].drop_duplicates().tolist(), reverse=True)
        resistances = sorted(pivots_df[pivots_df[pivot_col] == 1][price_col].drop_duplicates().tolist(), reverse=True)
        key_supports = [round(s, 5) for s in supports[:self.num_key_levels]]
        key_resistances = [round(r, 5) for r in resistances[:self.num_key_levels]]
        last_pivot = pivots_df.iloc[-1]
        last_pivot_type = "Support" if last_pivot[pivot_col] == -1 else "Resistance"
        nearest_support = next((s for s in key_supports if s < current_price), None)
        nearest_resistance = next((r for r in reversed(key_resistances) if r > current_price), None)
        dist_to_support = abs(current_price - nearest_support) if nearest_support is not None else None
        dist_to_resistance = abs(nearest_resistance - current_price) if nearest_resistance is not None else None
        position = "In Range"
        if dist_to_support is not None and dist_to_resistance is not None: position = "Closer to Support" if dist_to_support < dist_to_resistance else "Closer to Resistance"
        return { "status": "OK", "timeframe": self.timeframe or 'Base', "analysis": { "current_price": round(current_price, 5), "position": position, "last_pivot": { "type": last_pivot_type, "price": round(last_pivot[price_col], 5), "time": last_pivot.name.strftime('%Y-%m-%d %H:%M:%S') }, "proximity": { "nearest_support": nearest_support, "nearest_resistance": nearest_resistance, "distance_to_support_pct": round((dist_to_support / current_price) * 100, 2) if dist_to_support is not None else None, "distance_to_resistance_pct": round((dist_to_resistance / current_price) * 100, 2) if dist_to_resistance is not None else None } }, "key_levels": { "supports": key_supports, "resistances": key_resistances } }
