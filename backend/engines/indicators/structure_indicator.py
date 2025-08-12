import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, List, Optional

from .base import BaseIndicator
from .zigzag import ZigzagIndicator # Import ZigzagIndicator to call its static method

logger = logging.getLogger(__name__)

class StructureIndicator(BaseIndicator):
    """
    Market Structure Analyzer - (v5.0 - Multi-Version Aware)
    -----------------------------------------------------------------------------------------
    This world-class version is now fully compatible with the IndicatorAnalyzer v9.0's
    Multi-Version Engine. It intelligently reads its dependency configuration
    to request data from the specific version of ZigZag it needs.
    """
    # ✅ MIRACLE UPGRADE: Dependency is now declared in config, not hardcoded here.
    dependencies: list = []

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.timeframe = self.params.get('timeframe', None)
        self.num_key_levels = int(self.params.get('num_key_levels', 10))
        self.zone_proximity_pct = float(self.params.get('zone_proximity_pct', 0.1))

        # ✅ MIRACLE UPGRADE: The indicator now reads its specific dependency config.
        self.zigzag_dependency_params = self.params.get('dependencies', {}).get('zigzag', {'deviation': 3.0})

    def calculate(self) -> 'StructureIndicator':
        """ This indicator is a pure analyzer; no calculation needed here. """
        return self

    def _cluster_pivots_into_zones(self, pivots: List[float]) -> List[Dict[str, Any]]:
        """ A powerful helper to group close pivots into a single S/R zone and score its strength. """
        if not pivots: return []
        
        pivots = sorted(pivots)
        zones = []
        current_zone_pivots = [pivots[0]]
        
        for i in range(1, len(pivots)):
            zone_avg = np.mean(current_zone_pivots)
            if abs(pivots[i] - zone_avg) / zone_avg * 100 < self.zone_proximity_pct:
                current_zone_pivots.append(pivots[i])
            else:
                zones.append({'price': np.mean(current_zone_pivots), 'strength': len(current_zone_pivots)})
                current_zone_pivots = [pivots[i]]
        
        zones.append({'price': np.mean(current_zone_pivots), 'strength': len(current_zone_pivots)})
        return sorted(zones, key=lambda x: x['strength'], reverse=True)

    def analyze(self) -> Dict[str, Any]:
        """ Performs a full market structure analysis, including S/R Zone Strength. """
        # ✅ MIRACLE UPGRADE: Generates the required column names dynamically
        # based on its dependency's parameters, using the dependency's own static methods.
        pivot_col = ZigzagIndicator.get_pivots_col_name(self.zigzag_dependency_params, self.timeframe)
        price_col = ZigzagIndicator.get_prices_col_name(self.zigzag_dependency_params, self.timeframe)

        if not all(col in self.df.columns for col in [pivot_col, price_col]):
            logger.warning(f"[{self.__class__.__name__}] Missing ZigZag columns on timeframe {self.timeframe}. Required: {pivot_col}, {price_col}")
            return {"status": "Error: Missing Dependency Columns"}

        if len(self.df) < 2: return {"status": "Insufficient Data"}
        
        last_closed_candle = self.df.iloc[-2]
        current_price = last_closed_candle['close']
        
        valid_df = self.df.dropna(subset=[pivot_col, price_col])
        pivots_df = valid_df[valid_df[pivot_col] != 0]

        if len(pivots_df) < 2: return {"status": "Awaiting Pivots"}

        # The powerful "Fortress Engine" logic remains unchanged.
        all_supports_raw = pivots_df[pivots_df[pivot_col] == -1][price_col].tolist()
        all_resistances_raw = pivots_df[pivots_df[pivot_col] == 1][price_col].tolist()
        support_zones = self._cluster_pivots_into_zones(all_supports_raw)
        resistance_zones = self._cluster_pivots_into_zones(all_resistances_raw)
        key_supports = support_zones[:self.num_key_levels]
        key_resistances = resistance_zones[:self.num_key_levels]

        last_pivot = pivots_df.iloc[-1]
        last_pivot_type = "Support" if last_pivot[pivot_col] == -1 else "Resistance"
        
        nearest_support_zone = min([s for s in support_zones if s['price'] < current_price], key=lambda x: current_price - x['price'], default=None)
        nearest_resistance_zone = min([r for r in resistance_zones if r['price'] > current_price], key=lambda x: x['price'] - current_price, default=None)

        dist_to_support = abs(current_price - nearest_support_zone['price']) if nearest_support_zone else None
        dist_to_resistance = abs(nearest_resistance_zone['price'] - current_price) if nearest_resistance_zone else None
        
        position = "In Range"
        if dist_to_support is not None and dist_to_resistance is not None:
             if dist_to_support < dist_to_resistance: position = "Closer to Support"
             else: position = "Closer to Resistance"

        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "analysis": {
                "current_price": round(current_price, 5),
                "position": position,
                "last_pivot": {"type": last_pivot_type, "price": round(last_pivot[price_col], 5)},
                "proximity": {
                    "nearest_support_details": nearest_support_zone,
                    "nearest_resistance_details": nearest_resistance_zone,
                    "is_testing_support": dist_to_support / current_price * 100 < self.zone_proximity_pct if dist_to_support else False,
                    "is_testing_resistance": dist_to_resistance / current_price * 100 < self.zone_proximity_pct if dist_to_resistance else False
                }
            },
            "key_levels": { "supports": key_supports, "resistances": key_resistances }
        }
