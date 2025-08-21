# backend/engines/indicators/fibonacci.py (v6.0 - The Precision Edition)
import logging
import pandas as pd
import json
from typing import Dict, Any, Optional

from .base import BaseIndicator
from .utils import get_indicator_config_key

logger = logging.getLogger(__name__)

class FibonacciIndicator(BaseIndicator):
    """
    Fibonacci Analysis Suite - (v6.0 - The Precision Edition)
    -------------------------------------------------------------------------
    This definitive version fixes a critical regression bug by changing the
    current price lookup from iloc[-2] to iloc[-1]. This aligns the indicator
    perfectly with the 'Fresh Data Protocol' of the modern ExchangeFetcher,
    ensuring all analyses are performed on the absolute latest closed candle
    for maximum precision and relevance.
    """
    dependencies: list = ['zigzag']

    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], **kwargs):
        super().__init__(df, params=params, **kwargs)
        self.timeframe = self.params.get('timeframe')
        self.retracement_levels = sorted(self.params.get('retracements', [0, 23.6, 38.2, 50, 61.8, 78.6, 100]))
        self.extension_levels = sorted(self.params.get('extensions', [127.2, 161.8, 200, 261.8]))
        
        # Correctly handle set from config
        raw_golden_zone = self.params.get('golden_zone', ["50%", "61.8%"])
        self.golden_zone_levels = {str(level).replace('%', '') for level in raw_golden_zone}

        self.zigzag_instance: Optional[BaseIndicator] = None

    def calculate(self) -> 'FibonacciIndicator':
        """
        Prepares the indicator by linking to its ZigZag dependency.
        No calculation is done here; all logic is in analyze().
        """
        my_deps_config = self.params.get("dependencies", {})
        zigzag_order_params = my_deps_config.get('zigzag')
        if not zigzag_order_params:
            logger.error(f"[{self.__class__.__name__}] on {self.timeframe} cannot run: 'zigzag' dependency not defined in config.")
            return self
        
        zigzag_unique_key = get_indicator_config_key('zigzag', zigzag_order_params)
        self.zigzag_instance = self.dependencies.get(zigzag_unique_key)

        if not isinstance(self.zigzag_instance, BaseIndicator):
            logger.warning(f"[{self.__class__.__name__}] on {self.timeframe} missing critical ZigZag instance ('{zigzag_unique_key}').")
        
        return self

    def analyze(self) -> Dict[str, Any]:
        """ 
        Performs a full, on-the-fly Fibonacci analysis using the latest
        CONFIRMED pivots from the ZigZag indicator.
        """
        if not self.zigzag_instance:
            return {"status": "Calculation Incomplete - ZigZag dependency missing"}

        # Use the already-analyzed data from the ZigZag instance
        zigzag_analysis = self.zigzag_instance.analyze()
        zigzag_values = zigzag_analysis.get('values', {})

        # Rely on ZigZag v8.0+'s confirmed pivot logic
        start_pivot = zigzag_values.get('previous_confirmed_pivot')
        end_pivot = zigzag_values.get('last_confirmed_pivot')

        if not start_pivot or not end_pivot:
            return {'status': 'Insufficient Confirmed Pivots'}

        start_price = start_pivot['price']
        end_price = end_pivot['price']
        price_diff = end_price - start_price

        swing_trend = zigzag_values.get('swing_trend', 'Unknown')
        if swing_trend not in ["Up", "Down"]:
            return {'status': 'Neutral Swing', 'values': zigzag_values}

        swing_info = {
            "start_price": round(start_price, 5), "start_time": start_pivot['time'],
            "end_price": round(end_price, 5), "end_time": end_pivot['time']
        }

        levels = []
        for level in self.retracement_levels:
            price = end_price - (price_diff * (level / 100.0))
            levels.append({"level": f"{level}%", "price": round(price, 5), "type": "Retracement"})
        for level in self.extension_levels:
            price = end_price + (price_diff * ((level - 100) / 100.0))
            levels.append({"level": f"{level}%", "price": round(price, 5), "type": "Extension"})
        
        try:
            # ✅ PRECISION FIX (v6.0): Use iloc[-1] as the 'Fresh Data Protocol' ensures this is the last CLOSED candle.
            current_price = self.df.iloc[-1]['close']
        except IndexError:
            return {"status": "Insufficient Data for Current Price"}
        
        position = "Outside Retracement Zone"
        in_golden_zone = False
        retracement_levels_only = [lvl for lvl in levels if lvl['type'] == 'Retracement']
        sorted_levels = sorted(retracement_levels_only, key=lambda x: x['price'], reverse=(swing_trend == "Up"))
        
        for i in range(len(sorted_levels) - 1):
            upper_level, lower_level = sorted_levels[i], sorted_levels[i+1]
            if min(lower_level['price'], upper_level['price']) <= current_price <= max(lower_level['price'], upper_level['price']):
                position = f"Between {lower_level['level']} and {upper_level['level']}"
                upper_level_str = upper_level['level'].replace('%', '')
                lower_level_str = lower_level['level'].replace('%', '')
                
                # Check if BOTH golden zone levels are represented by the current zone's boundaries
                if self.golden_zone_levels.issubset({upper_level_str, lower_level_str}):
                    in_golden_zone = True
                break
        
        analysis_content = {
            'swing_trend': swing_trend, 'swing_details': swing_info,
            'levels': levels,
            'analysis': {
                'current_price': round(current_price, 5),
                'position': position,
                'is_in_golden_zone': in_golden_zone
            }
        }

        return {
            'status': 'OK', 'timeframe': self.timeframe or 'Base',
            'values': analysis_content,
            'analysis': analysis_content # For backward compatibility
        }
