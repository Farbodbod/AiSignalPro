# backend/engines/indicators/fibonacci.py
import logging
import pandas as pd
import json
from typing import Dict, Any

from .base import BaseIndicator
from .utils import get_indicator_config_key # ✅ World-Class Practice: Import from shared utils

logger = logging.getLogger(__name__)

class FibonacciIndicator(BaseIndicator):
    """
    Fibonacci Analysis Suite - (v5.2 - Unified Utils)
    -------------------------------------------------------------------------
    This definitive version is fully DI-native and hardened. It no longer contains
    a local copy of the helper functions, instead importing them from the shared
    `utils.py` module, adhering to the DRY principle and professional software
    engineering standards. All logic is 100% preserved.
    """
    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], dependencies: Dict[str, BaseIndicator], **kwargs):
        super().__init__(df, params=params, dependencies=dependencies, **kwargs)
        self.timeframe = self.params.get('timeframe')
        self.retracement_levels = sorted(self.params.get('retracements', [0, 23.6, 38.2, 50, 61.8, 78.6, 100]))
        self.extension_levels = sorted(self.params.get('extensions', [127.2, 161.8, 200, 261.8]))
        raw_golden_zone = self.params.get('golden_zone', {'61.8%', '78.6%'})
        self.golden_zone_levels = {str(level).replace('%', '') for level in raw_golden_zone}

        self.pivot_col: str | None = None
        self.price_col: str | None = None

    def calculate(self) -> 'FibonacciIndicator':
        """
        Prepares the indicator's DataFrame by correctly looking up its ZigZag dependency.
        """
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

    def analyze(self) -> Dict[str, Any]:
        """ 
        Performs a full, on-the-fly Fibonacci analysis. The entire analytical
        logic is 100% preserved and now protected by a guard clause.
        """
        if not self.pivot_col or not self.price_col or not all(col in self.df.columns for col in [self.pivot_col, self.price_col]):
            return {"status": "Calculation Incomplete - Required columns missing"}

        valid_df = self.df.dropna(subset=[self.pivot_col, self.price_col])
        pivots_df = valid_df[valid_df[self.pivot_col] != 0]

        if len(pivots_df) < 2:
            return {'status': 'Insufficient Pivots'}

        last_pivot = pivots_df.iloc[-1]
        prev_pivot = pivots_df.iloc[-2]
        start_price = prev_pivot[self.price_col]
        end_price = last_pivot[self.price_col]
        price_diff = end_price - start_price

        swing_trend = "Neutral"
        if price_diff > 0: swing_trend = "Up"
        elif price_diff < 0: swing_trend = "Down"

        swing_info = {
            "start_price": round(start_price, 5), "start_time": prev_pivot.name.strftime('%Y-%m-%d %H:%M:%S'),
            "end_price": round(end_price, 5), "end_time": last_pivot.name.strftime('%Y-%m-%d %H:%M:%S')
        }

        if swing_trend == "Neutral":
            return {'status': 'Neutral Swing', 'swing_trend': swing_trend, 'swing_details': swing_info}

        levels = []
        for level in self.retracement_levels:
            price = end_price - (price_diff * (level / 100.0))
            levels.append({"level": f"{level}%", "price": round(price, 5), "type": "Retracement"})
        for level in self.extension_levels:
            price = end_price + (price_diff * ((level - 100) / 100.0))
            levels.append({"level": f"{level}%", "price": round(price, 5), "type": "Extension"})
        
        if len(self.df) < 2: return {"status": "Insufficient Data"}
        current_price = self.df.iloc[-2]['close']
        
        position = "Outside Retracement Zone"
        in_golden_zone = False
        retracement_levels_only = [lvl for lvl in levels if lvl['type'] == 'Retracement']
        sorted_levels = sorted(retracement_levels_only, key=lambda x: x['price'], reverse=(swing_trend == "Up"))
        
        for i in range(len(sorted_levels) - 1):
            upper_level, lower_level = sorted_levels[i], sorted_levels[i+1]
            if min(lower_level['price'], upper_level['price']) <= current_price <= max(lower_level['price'], upper_level['price']):
                position = f"Between {lower_level['level']} and {upper_level['level']}"
                current_zone_levels = {lvl['level'].replace('%', '') for lvl in [upper_level, lower_level]}
                if self.golden_zone_levels.issubset(current_zone_levels):
                    in_golden_zone = True
                break
        
        return {
            'status': 'OK', 'timeframe': self.timeframe or 'Base',
            'swing_trend': swing_trend, 'swing_details': swing_info,
            'analysis': {
                'current_price': round(current_price, 5),
                'position': position,
                'is_in_golden_zone': in_golden_zone
            },
            'levels': levels
        }
