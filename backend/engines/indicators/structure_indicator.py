# backend/engines/indicators/structure_indicator.py (v7.1 - The Final Hotfix)
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, List

from .base import BaseIndicator
from .utils import get_indicator_config_key

logger = logging.getLogger(__name__)

class StructureIndicator(BaseIndicator):
    """
    Market Structure Analyzer - (v7.1 - The Final Hotfix)
    -----------------------------------------------------------------------------------------
    This definitive version contains the final architectural hotfix. The 'key_levels'
    output is now promoted to the root level of the analysis package, making it
    directly accessible to the MasterOrchestrator and SignalAdapter, thus fixing
    the "Not Available" bug in all signals. All previous features and hardening
    patches are 100% preserved.
    """
    dependencies: list = ['zigzag']
    
    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], **kwargs):
        super().__init__(df, params=params, **kwargs)
        self.timeframe = self.params.get('timeframe')
        self.num_key_levels = int(self.params.get('num_key_levels', 10))
        self.zone_proximity_pct = float(self.params.get('zone_proximity_pct', 0.1))
        self.zigzag_instance: BaseIndicator | None = None

    def calculate(self) -> 'StructureIndicator':
        # ... [This method is unchanged and correct] ...
        my_deps_config = self.params.get("dependencies", {})
        zigzag_order_params = my_deps_config.get('zigzag')
        if not zigzag_order_params:
            logger.error(f"[{self.__class__.__name__}] on {self.timeframe}: 'zigzag' dependency not defined in config.")
            return self
        
        zigzag_unique_key = get_indicator_config_key('zigzag', zigzag_order_params)
        self.zigzag_instance = self.dependencies.get(zigzag_unique_key)

        if not isinstance(self.zigzag_instance, BaseIndicator):
            logger.warning(f"[{self.__class__.__name__}] on {self.timeframe}: missing critical ZigZag instance ('{zigzag_unique_key}').")
        return self

    def _cluster_pivots_into_zones(self, pivots: List[float]) -> List[Dict[str, Any]]:
        # ... [This method is unchanged and correct] ...
        if not pivots: return []
        pivots = sorted(pivots)
        zones = []
        current_zone_pivots = [pivots[0]]
        for i in range(1, len(pivots)):
            zone_avg = np.mean(current_zone_pivots)
            safe_zone_avg = max(zone_avg, 1e-12)
            if abs(pivots[i] - zone_avg) / safe_zone_avg * 100 < self.zone_proximity_pct:
                current_zone_pivots.append(pivots[i])
            else:
                zones.append({'price': np.mean(current_zone_pivots), 'strength': len(current_zone_pivots)})
                current_zone_pivots = [pivots[i]]
        zones.append({'price': np.mean(current_zone_pivots), 'strength': len(current_zone_pivots)})
        return sorted(zones, key=lambda x: x['strength'], reverse=True)

    def analyze(self) -> Dict[str, Any]:
        analysis_content = {"analysis": {}, "key_levels": {}}
        if not self.zigzag_instance:
            return {"status": "Calculation Incomplete - ZigZag dependency missing", "key_levels": {}, "values": analysis_content, "analysis": analysis_content}

        zigzag_analysis = self.zigzag_instance.analyze()
        if zigzag_analysis.get('status') != 'OK':
            return {"status": f"Awaiting Pivots from ZigZag ({zigzag_analysis.get('status')})", "key_levels": {}, "values": analysis_content, "analysis": analysis_content}
        
        try:
            current_price = self.df.iloc[-1]['close']
        except IndexError:
            return {"status": "Insufficient Data for Current Price", "key_levels": {}, "values": analysis_content, "analysis": analysis_content}

        pivots_df = self.zigzag_instance.df[self.zigzag_instance.df[self.zigzag_instance.pivots_col] != 0]
        
        all_supports_raw = pivots_df[pivots_df[self.zigzag_instance.pivots_col] == -1][self.zigzag_instance.prices_col].tolist()
        all_resistances_raw = pivots_df[pivots_df[self.zigzag_instance.pivots_col] == 1][self.zigzag_instance.prices_col].tolist()
        support_zones = self._cluster_pivots_into_zones(all_supports_raw)
        resistance_zones = self._cluster_pivots_into_zones(all_resistances_raw)
        key_supports = support_zones[:self.num_key_levels]
        key_resistances = resistance_zones[:self.num_key_levels]

        last_pivot_info = (zigzag_analysis.get('values') or {}).get('candidate_pivot', {})
        last_pivot_type = "Support" if last_pivot_info.get('type') == 'trough' else "Resistance"
        
        nearest_support_zone = min([s for s in support_zones if s['price'] < current_price], key=lambda x: current_price - x['price'], default=None)
        nearest_resistance_zone = min([r for r in resistance_zones if r['price'] > current_price], key=lambda x: x['price'] - current_price, default=None)

        dist_to_support = abs(current_price - nearest_support_zone['price']) if nearest_support_zone else None
        dist_to_resistance = abs(nearest_resistance_zone['price'] - current_price) if nearest_resistance_zone else None
        
        position = "In Range"
        if dist_to_support is not None and dist_to_resistance is not None:
             if dist_to_support < dist_to_resistance: position = "Closer to Support"
             else: position = "Closer to Resistance"

        # Prepare the individual components of the output
        analysis_details = {
            "current_price": round(current_price, 5),
            "position": position,
            "last_pivot": {"type": last_pivot_type, "price": round(last_pivot_info.get('price', 0), 5)},
            "proximity": {
                "nearest_support_details": nearest_support_zone,
                "nearest_resistance_details": nearest_resistance_zone,
                "is_testing_support": dist_to_support / current_price * 100 < self.zone_proximity_pct if dist_to_support is not None and current_price > 0 else False,
                "is_testing_resistance": dist_to_resistance / current_price * 100 < self.zone_proximity_pct if dist_to_resistance is not None and current_price > 0 else False
            }
        }
        key_levels_data = { "supports": key_supports, "resistances": key_resistances }

        # ✅ THE FINAL HOTFIX (v7.1): Assemble the final dictionary with 'key_levels' at the root.
        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "key_levels": key_levels_data,  # Promoted to the root level for system-wide access
            "values": {                     # Original structure preserved for compatibility
                "analysis": analysis_details,
                "key_levels": key_levels_data
            },
            "analysis": {                   # Original structure preserved for compatibility
                "analysis": analysis_details,
                "key_levels": key_levels_data
            }
        }

