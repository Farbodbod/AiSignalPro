import logging
import pandas as pd
from .base import BaseIndicator
from .zigzag import ZigzagIndicator

logger = logging.getLogger(__name__)

class FibonacciIndicator(BaseIndicator):
    """
    Fibonacci Analysis Suite - World-Class & Intelligent Version
    --------------------------------------------------------------
    This version includes:
    1.  Calculation of both Retracement and Extension levels.
    2.  Intelligent analysis of price position, including the "Golden Zone".
    3.  Robust, universal JSON output (list of objects).
    4.  Bulletproof handling of edge cases (low data, neutral trend).
    5.  Clean architecture by separating calculation from analysis.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.swing_info = {}
        self.levels = []  # ✨ IMPROVEMENT: Using a list of dicts for guaranteed JSON order
        self.trend = "AwaitingCalculation"

        # ✨ IMPROVEMENT: Allow user to define retracement and extension levels
        self.params = kwargs.get('params', {})
        self.retracement_levels = sorted(self.params.get('retracements', [0, 23.6, 38.2, 50, 61.8, 78.6, 100]))
        self.extension_levels = sorted(self.params.get('extensions', [127.2, 161.8, 200, 261.8]))
        self.zigzag_deviation = self.params.get('zigzag_deviation', 3.0)

    def _validate_and_get_pivots(self):
        """Uses our robust Zigzag to find the last two significant pivots."""
        if self.df[['high', 'low', 'close']].isnull().any().any():
            logger.warning("Missing OHLC data detected. Fibonacci calculation might be affected.")
            self.df.dropna(subset=['high', 'low', 'close'], inplace=True)

        zigzag = ZigzagIndicator(self.df, params={'deviation': self.zigzag_deviation})
        zigzag_df = zigzag.calculate()
        
        pivot_col = f'zigzag_pivots_{self.zigzag_deviation}'
        pivots_df = zigzag_df[zigzag_df[pivot_col] != 0]

        if len(pivots_df) < 2:
            logger.warning("Not enough pivots found by ZigZag for Fibonacci calculation.")
            return None, None
            
        return pivots_df.iloc[-1], pivots_df.iloc[-2]

    def calculate(self) -> pd.DataFrame:
        """Calculates Fibonacci levels based on the last significant market swing."""
        last_pivot, prev_pivot = self._validate_and_get_pivots()

        if last_pivot is None:
            self.trend = "Neutral"
            self.swing_info = {"message": "Not enough data or pivots."}
            return self.df # ✅ FIX: Only one return point at the end of logic flow

        start_price = prev_pivot[f'zigzag_prices_{self.zigzag_deviation}']
        end_price = last_pivot[f'zigzag_prices_{self.zigzag_deviation}']
        price_diff = end_price - start_price

        if price_diff > 0: self.trend = "Up"
        elif price_diff < 0: self.trend = "Down"
        else: self.trend = "Neutral"; return self.df

        # --- Calculate Levels ---
        self.levels = [] # Clear previous levels
        # Retracements
        for level in self.retracement_levels:
            price = end_price - (price_diff * (level / 100.0))
            self.levels.append({"level": f"{level}%", "price": round(price, 5), "type": "Retracement"})
        # Extensions
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
        return self.df

    def analyze(self) -> dict:
        """Provides a deep, intelligent analysis of the current price against Fibonacci levels."""
        if not self.levels:
            return {'indicator': self.__class__.__name__, **self.swing_info}

        current_price = self.df['close'].iloc[-1]
        price_position = "Outside known levels"
        in_golden_zone = False

        # Sort levels by price for accurate position finding
        sorted_levels = sorted(self.levels, key=lambda x: x['price'], reverse=(self.trend == "Up"))
        
        for i in range(len(sorted_levels) - 1):
            upper_level = sorted_levels[i]
            lower_level = sorted_levels[i+1]
            
            if lower_level['price'] <= current_price <= upper_level['price']:
                price_position = f"Between {lower_level['level']} and {upper_level['level']}"
                # ✨ IMPROVEMENT: Golden Zone Detection
                if {'50%', '61.8%'}.issubset({lower_level['level'], upper_level['level']}) or \
                   {'61.8%', '78.6%'}.issubset({lower_level['level'], upper_level['level']}):
                    in_golden_zone = True
                break

        return {
            'indicator': self.__class__.__name__,
            'swing_trend': self.trend,
            'swing_details': self.swing_info,
            'analysis': {
                'current_price': round(current_price, 5),
                'position': price_position,
                'is_in_golden_zone': in_golden_zone
            },
            'levels': self.levels
        }
