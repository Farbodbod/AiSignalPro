import logging
import pandas as pd
from typing import Dict, Any, List, Optional
from .base import BaseIndicator
from .zigzag import ZigzagIndicator

logger = logging.getLogger(__name__)

class FibonacciIndicator(BaseIndicator):
    """ Fibonacci Analysis Suite - Definitive, MTF & World-Class Version (v2.1 - Bugfix) """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.swing_info: Dict[str, Any] = {}; self.levels: List[Dict[str, Any]] = []
        self.trend = "AwaitingCalculation"; self.params = kwargs.get('params', {})
        self.timeframe = self.params.get('timeframe', None)
        self.retracement_levels = sorted(self.params.get('retracements', [0, 23.6, 38.2, 50, 61.8, 78.6, 100]))
        self.extension_levels = sorted(self.params.get('extensions', [127.2, 161.8, 200, 261.8]))
        self.zigzag_deviation = self.params.get('zigzag_deviation', 3.0)
        self.golden_zone_levels = self.params.get('golden_zone', {'61.8%', '78.6%'})
        self._zigzag_instance: Optional[ZigzagIndicator] = None

    def calculate(self) -> 'FibonacciIndicator':
        zigzag_params = {'deviation': self.zigzag_deviation, 'timeframe': self.timeframe}
        zigzag_instance = ZigzagIndicator(self.df, params=zigzag_params).calculate()
        self.df = zigzag_instance.df
        self._zigzag_instance = zigzag_instance
        
        pivot_col = self._zigzag_instance.col_pivots; price_col = self._zigzag_instance.col_prices
        pivots_df = self.df[self.df[pivot_col] != 0]

        if len(pivots_df) < 2:
            self.trend = "Neutral"; self.swing_info = {"message": "Not enough pivots"}; self.levels = []
            return self

        last_pivot = pivots_df.iloc[-1]; prev_pivot = pivots_df.iloc[-2]
        start_price = prev_pivot[price_col]; end_price = last_pivot[price_col]
        price_diff = end_price - start_price

        if price_diff > 0: self.trend = "Up"
        elif price_diff < 0: self.trend = "Down"
        else: self.trend = "Neutral"; self.levels = []; return self
        
        self.levels = []
        for level in self.retracement_levels:
            price = end_price - (price_diff * (level / 100.0))
            self.levels.append({"level": f"{level}%", "price": round(price, 5), "type": "Retracement"})
        for level in self.extension_levels:
            price = end_price + (price_diff * ((level - 100) / 100.0))
            self.levels.append({"level": f"{level}%", "price": round(price, 5), "type": "Extension"})
            
        self.swing_info = { "start_price": round(start_price, 5), "start_time": prev_pivot.name.strftime('%Y-%m-%d %H:%M:%S'), "end_price": round(end_price, 5), "end_time": last_pivot.name.strftime('%Y-%m-%d %H:%M:%S') }
        return self

    def analyze(self) -> Dict[str, Any]:
        if not self.levels: return {'indicator': self.__class__.__name__, 'timeframe': self.timeframe, 'status': 'No Levels Calculated', 'swing_details': self.swing_info}
        current_price = self.df.iloc[-2]['close'] # Bias-free
        position = "Outside Retracement Zone"; in_golden_zone = False
        retracement_levels = [lvl for lvl in self.levels if lvl['type'] == 'Retracement']
        sorted_levels = sorted(retracement_levels, key=lambda x: x['price'], reverse=(self.trend == "Up"))
        for i in range(len(sorted_levels) - 1):
            upper_level, lower_level = sorted_levels[i], sorted_levels[i+1]
            if min(lower_level['price'], upper_level['price']) <= current_price <= max(lower_level['price'], upper_level['price']):
                position = f"Between {lower_level['level']} and {upper_level['level']}"
                if self.golden_zone_levels.issubset({lower_level['level'], upper_level['level']}): in_golden_zone = True
                break
        return { 'indicator': self.__class__.__name__, 'timeframe': self.timeframe or 'Base', 'status': 'OK', 'swing_trend': self.trend, 'swing_details': self.swing_info, 'analysis': { 'current_price': round(current_price, 5), 'position': position, 'is_in_golden_zone': in_golden_zone }, 'levels': self.levels }
