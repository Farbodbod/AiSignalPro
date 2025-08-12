import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

from .base import BaseIndicator

class StructureIndicator(BaseIndicator):
    """
    Market Structure Analyzer - (v4.0 - Fortress Engine)
    -----------------------------------------------------------------------------------------
    This world-class version evolves from a simple level-finder to a "Fortress"
    detection engine. It quantifies the strength of each S/R level based on the
    number of historical touches, providing critical data for high-probability
    reversal strategies like the DivergenceSniperPro.
    """
    dependencies = ['zigzag']

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.zigzag_deviation = float(self.params.get('zigzag_deviation', 3.0))
        self.timeframe = self.params.get('timeframe', None)
        self.num_key_levels = int(self.params.get('num_key_levels', 10))
        self.zone_proximity_pct = float(self.params.get('zone_proximity_pct', 0.1)) # 0.1% proximity to group pivots into a zone

    def calculate(self) -> 'StructureIndicator':
        """ This indicator is a pure analyzer; no calculation needed here. """
        return self

    def _cluster_pivots_into_zones(self, pivots: List[float]) -> List[Dict[str, Any]]:
        """ A powerful helper to group close pivots into a single S/R zone and score its strength. """
        if not pivots: return []
        
        # Sort pivots to ensure logical clustering
        pivots = sorted(pivots)
        
        zones = []
        current_zone_pivots = [pivots[0]]
        
        for i in range(1, len(pivots)):
            # Check if the next pivot is close enough to the current zone's average
            zone_avg = np.mean(current_zone_pivots)
            if abs(pivots[i] - zone_avg) / zone_avg * 100 < self.zone_proximity_pct:
                current_zone_pivots.append(pivots[i])
            else:
                # Finalize the current zone and start a new one
                zones.append({'price': np.mean(current_zone_pivots), 'strength': len(current_zone_pivots)})
                current_zone_pivots = [pivots[i]]
        
        # Add the last zone
        zones.append({'price': np.mean(current_zone_pivots), 'strength': len(current_zone_pivots)})
        
        # Sort final zones by strength, descending
        return sorted(zones, key=lambda x: x['strength'], reverse=True)

    def analyze(self) -> Dict[str, Any]:
        """ Performs a full market structure analysis, now including S/R Zone Strength. """
        tf_suffix = f'_{self.timeframe}' if self.timeframe else ''
        pivot_col = f'zigzag_pivots_{self.zigzag_deviation}{tf_suffix}'
        price_col = f'zigzag_prices_{self.zigzag_deviation}{tf_suffix}'

        if not all(col in self.df.columns for col in [pivot_col, price_col]):
            return {"status": "Error: Missing Dependency Columns"}

        if len(self.df) < 2: return {"status": "Insufficient Data"}
        
        last_closed_candle = self.df.iloc[-2]
        current_price = last_closed_candle['close']
        
        valid_df = self.df.dropna(subset=[pivot_col, price_col])
        pivots_df = valid_df[valid_df[pivot_col] != 0]

        if len(pivots_df) < 2: return {"status": "Awaiting Pivots"}

        # --- ✅ MIRACLE UPGRADE: From simple levels to scored zones ---
        all_supports_raw = pivots_df[pivots_df[pivot_col] == -1][price_col].tolist()
        all_resistances_raw = pivots_df[pivots_df[pivot_col] == 1][price_col].tolist()

        support_zones = self._cluster_pivots_into_zones(all_supports_raw)
        resistance_zones = self._cluster_pivots_into_zones(all_resistances_raw)
        
        key_supports = support_zones[:self.num_key_levels]
        key_resistances = resistance_zones[:self.num_key_levels]

        # --- Analysis based on the new, powerful zone data ---
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
