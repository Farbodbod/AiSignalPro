import logging
import pandas as pd
from typing import Dict, Any, List

# اطمینان حاصل کنید که این اندیکاتورها از فایل‌های مربوطه وارد شده‌اند
from .base import BaseIndicator
from .zigzag import ZigzagIndicator # نسخه MTF-capable

logger = logging.getLogger(__name__)

class FibonacciIndicator(BaseIndicator):
    """
    Fibonacci Analysis Suite - Definitive MTF & World-Class Version
    -----------------------------------------------------------------
    This version supports Multi-Timeframe analysis by passing the timeframe
    parameter down to its ZigZag dependency. It retains all advanced features
    like Retracement/Extension levels and Golden Zone analysis.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        # --- State ---
        self.swing_info: Dict[str, Any] = {}
        self.levels: List[Dict[str, Any]] = []
        self.trend = "AwaitingCalculation"

        # --- Parameters ---
        self.params = kwargs.get('params', {})
        self.timeframe = self.params.get('timeframe', None) # Master timeframe
        self.retracement_levels = sorted(self.params.get('retracements', [0, 23.6, 38.2, 50, 61.8, 78.6, 100]))
        self.extension_levels = sorted(self.params.get('extensions', [127.2, 161.8, 200, 261.8]))
        self.zigzag_deviation = self.params.get('zigzag_deviation', 3.0)

    def calculate(self) -> 'FibonacciIndicator':
        """Calculates Fibonacci levels based on the last significant swing, supporting MTF."""
        # ✨ MTF LOGIC: Pass the timeframe down to the ZigZag dependency
        zigzag_params = {
            'deviation': self.zigzag_deviation,
            'timeframe': self.timeframe
        }
        zigzag = ZigzagIndicator(self.df, params=zigzag_params)
        zigzag_df = zigzag.calculate()
        
        # Dynamically get column names from the dependency
        pivot_col = zigzag.col_pivots
        price_col = zigzag.col_prices
        
        pivots_df = zigzag_df[zigzag_df[pivot_col] != 0]

        if len(pivots_df) < 2:
            self.trend = "Neutral"
            self.swing_info = {"message": "Not enough pivots to calculate Fibonacci."}
            self.levels = []
            return self

        last_pivot = pivots_df.iloc[-1]
        prev_pivot = pivots_df.iloc[-2]

        start_price = prev_pivot[price_col]
        end_price = last_pivot[price_col]
        price_diff = end_price - start_price

        if price_diff > 0: self.trend = "Up"
        elif price_diff < 0: self.trend = "Down"
        else: self.trend = "Neutral"; self.levels = []; return self

        # --- Calculate Levels ---
        self.levels = []
        for level in self.retracement_levels:
            price = end_price - (price_diff * (level / 100.0))
            self.levels.append({"level": f"{level}%", "price": round(price, 5), "type": "Retracement"})
        for level in self.extension_levels:
            price = end_price + (price_diff * ((level - 100) / 100.0))
            self.levels.append({"level": f"{level}%", "price": round(price, 5), "type": "Extension"})

        # --- Store Swing Info ---
        self.swing_info = {
            "start_price": round(start_price, 5),
            "start_time": prev_pivot.name.strftime('%Y-%m-%d %H:%M:%S'),
            "end_price": round(end_price, 5),
            "end_time": last_pivot.name.strftime('%Y-%m-%d %H:%M:%S'),
        }
        return self

    def analyze(self) -> Dict[str, Any]:
        """Provides a deep, intelligent analysis of the current price against Fibonacci levels."""
        # ... (The world-class analyze logic remains unchanged, as it works on the calculated state)
        if not self.levels:
            return {'indicator': self.__class__.__name__, 'timeframe': self.timeframe, **self.swing_info}

        current_price = self.df['close'].iloc[-1]
        position = "Outside known levels"
        in_golden_zone = False

        sorted_levels = sorted(self.levels, key=lambda x: x['price'], reverse=(self.trend == "Up"))
        
        for i in range(len(sorted_levels) - 1):
            upper_level, lower_level = sorted_levels[i], sorted_levels[i+1]
            if lower_level['price'] <= current_price <= upper_level['price']:
                position = f"Between {lower_level['level']} and {upper_level['level']}"
                if {'61.8%', '78.6%'}.issubset({lower_level['level'], upper_level['level']}):
                    in_golden_zone = True
                break

        return {
            'indicator': self.__class__.__name__,
            'timeframe': self.timeframe or 'Base',
            'swing_trend': self.trend,
            'swing_details': self.swing_info,
            'analysis': {
                'current_price': round(current_price, 5),
                'position': position,
                'is_in_golden_zone': in_golden_zone
            },
            'levels': self.levels
        }
