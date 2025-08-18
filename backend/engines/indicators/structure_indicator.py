# backend/engines/indicators/structure_indicator.py
import pandas as pd
import numpy as np
import logging
import json
from typing import Dict, Any, List

from .base import BaseIndicator
from .utils import get_indicator_config_key # ✅ World-Class Practice: Import from shared utils

logger = logging.getLogger(__name__)

class StructureIndicator(BaseIndicator):
    """
    Market Structure Analyzer - (v6.1 - Definitive Dependency Hotfix)
    -----------------------------------------------------------------------------------------
    This version contains the definitive, world-class fix for dependency lookup.
    It now correctly reconstructs the unique_key of its dependency (ZigZag) from
    its own configuration, ensuring a flawless and robust connection to the
    data provider. The core clustering and analysis algorithms remain 100% intact.
    """
    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], dependencies: Dict[str, BaseIndicator], **kwargs):
        super().__init__(df, params=params, dependencies=dependencies, **kwargs)
        self.timeframe = self.params.get('timeframe')
        self.num_key_levels = int(self.params.get('num_key_levels', 10))
        self.zone_proximity_pct = float(self.params.get('zone_proximity_pct', 0.1))

        self.pivot_col: str | None = None
        self.price_col: str | None = None

    def calculate(self) -> 'StructureIndicator':
        """
        Prepares the indicator's DataFrame by correctly looking up its ZigZag dependency.
        """
        # ✅ DEFINITIVE FIX: The correct way to look up a dependency.
        my_deps_config = self.params.get("dependencies", {})
        zigzag_order_params = my_deps_config.get('zigzag')
        if not zigzag_order_params:
            logger.error(f"[{self.__class__.__name__}] on {self.timeframe} cannot run: 'zigzag' dependency not defined in config.")
            return self

        zigzag_unique_key = get_indicator_config_key('zigzag', zigzag_order_params)
        zigzag_instance = self.dependencies.get(zigzag_unique_key)

        if not isinstance(zigzag_instance, BaseIndicator):
            logger.warning(f"[{self.__class__.__name__}] on {self.timeframe} missing critical ZigZag instance ('{zigzag_unique_key}').")
            return self

        zigzag_df = zigzag_instance.df
        pivots_col_options = [col for col in zigzag_df.columns if 'PIVOTS' in col.upper()]
        prices_col_options = [col for col in zigzag_df.columns if 'PRICES' in col.upper()]

        if not pivots_col_options or not prices_col_options:
            logger.warning(f"[{self.__class__.__name__}] on {self.timeframe} could not find required columns in ZigZag dependency.")
            return self
            
        self.pivot_col = pivots_col_options[0]
        self.price_col = prices_col_options[0]

        self.df = self.df.join(zigzag_df[[self.pivot_col, self.price_col]], how='left')
        return self

    def _cluster_pivots_into_zones(self, pivots: List[float]) -> List[Dict[str, Any]]:
        """
        Core clustering algorithm. This method is 100% preserved from the previous version.
        """
        if not pivots: return []
        pivots = sorted(pivots)
        zones = []
        current_zone_pivots = [pivots[0]]
        for i in range(1, len(pivots)):
            zone_avg = np.mean(current_zone_pivots)
            # Safe division
            if zone_avg == 0: continue
            if abs(pivots[i] - zone_avg) / zone_avg * 100 < self.zone_proximity_pct:
                current_zone_pivots.append(pivots[i])
            else:
                zones.append({'price': np.mean(current_zone_pivots), 'strength': len(current_zone_pivots)})
                current_zone_pivots = [pivots[i]]
        zones.append({'price': np.mean(current_zone_pivots), 'strength': len(current_zone_pivots)})
        return sorted(zones, key=lambda x: x['strength'], reverse=True)

    def analyze(self) -> Dict[str, Any]:
        """
        Performs the full market structure analysis. The entire analytical logic is 100% preserved.
        """
        empty_analysis = {"analysis": {}, "key_levels": {}}

        if not self.pivot_col or not self.price_col or not all(col in self.df.columns for col in [self.pivot_col, self.price_col]):
            return {"status": "Calculation Incomplete - Required columns missing", **empty_analysis}

        if len(self.df) < 2:
            return {"status": "Insufficient Data", **empty_analysis}
        
        # Safe access to iloc
        if len(self.df) < 2: return {"status": "Insufficient Data", **empty_analysis}
        last_closed_candle = self.df.iloc[-2]
        current_price = last_closed_candle['close']
        
        valid_df = self.df.dropna(subset=[self.pivot_col, self.price_col])
        pivots_df = valid_df[valid_df[self.pivot_col] != 0]

        if len(pivots_df) < 2:
            return {"status": "Awaiting Pivots", **empty_analysis}

        all_supports_raw = pivots_df[pivots_df[self.pivot_col] == -1][self.price_col].tolist()
        all_resistances_raw = pivots_df[pivots_df[self.pivot_col] == 1][self.price_col].tolist()
        support_zones = self._cluster_pivots_into_zones(all_supports_raw)
        resistance_zones = self._cluster_pivots_into_zones(all_resistances_raw)
        key_supports = support_zones[:self.num_key_levels]
        key_resistances = resistance_zones[:self.num_key_levels]

        last_pivot = pivots_df.iloc[-1]
        last_pivot_type = "Support" if last_pivot[self.pivot_col] == -1 else "Resistance"
        
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
                "last_pivot": {"type": last_pivot_type, "price": round(last_pivot[self.price_col], 5)},
                "proximity": {
                    "nearest_support_details": nearest_support_zone,
                    "nearest_resistance_details": nearest_resistance_zone,
                    "is_testing_support": dist_to_support / current_price * 100 < self.zone_proximity_pct if dist_to_support is not None and current_price > 0 else False,
                    "is_testing_resistance": dist_to_resistance / current_price * 100 < self.zone_proximity_pct if dist_to_resistance is not None and current_price > 0 else False
                }
            },
            "key_levels": { "supports": key_supports, "resistances": key_resistances }
        }
