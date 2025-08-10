import logging
import pandas as pd
from typing import Dict, Any, List, Optional

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class FibonacciIndicator(BaseIndicator):
    """
    Fibonacci Analysis Suite - Definitive, MTF & World-Class Version (v3.0 - No Internal Deps)
    -----------------------------------------------------------------------------------------
    This version adheres to the final AiSignalPro architecture. It acts as a pure
    on-the-fly analysis engine, consuming pre-calculated ZigZag columns to identify
    the latest market swing and compute Fibonacci levels in real-time during analysis.
    """
    
    dependencies = ['zigzag']

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.timeframe = self.params.get('timeframe', None)
        self.retracement_levels = sorted(self.params.get('retracements', [0, 23.6, 38.2, 50, 61.8, 78.6, 100]))
        self.extension_levels = sorted(self.params.get('extensions', [127.2, 161.8, 200, 261.8]))
        self.zigzag_deviation = float(self.params.get('zigzag_deviation', 3.0))
        self.golden_zone_levels = self.params.get('golden_zone', {'61.8%', '78.6%'})

 

    def calculate(self) -> 'FibonacciIndicator':
        """
        ✨ FINAL ARCHITECTURE: This indicator is a pure analyzer.
        It does not calculate any new columns itself. It relies on columns
        pre-calculated by the IndicatorAnalyzer.
        """
        return self

    def analyze(self) -> Dict[str, Any]:
        """
        Performs a full, on-the-fly Fibonacci analysis based on the latest
        pre-calculated ZigZag pivots.
        """
        # --- 1. Construct required column names and validate their existence ---
        tf_suffix = f'_{self.timeframe}' if self.timeframe else ''
        pivot_col = f'zigzag_pivots_{self.zigzag_deviation}{tf_suffix}'
        price_col = f'zigzag_prices_{self.zigzag_deviation}{tf_suffix}'

        if not all(col in self.df.columns for col in [pivot_col, price_col]):
            logger.warning(f"[{self.__class__.__name__}] Missing ZigZag columns for analysis on timeframe {self.timeframe}.")
            return {"status": "Error: Missing Dependency Columns"}

        # --- 2. Find last swing from ZigZag pivots ---
        valid_df = self.df.dropna(subset=[pivot_col, price_col])
        pivots_df = valid_df[valid_df[pivot_col] != 0]

        if len(pivots_df) < 2:
            return {'status': 'Insufficient Pivots', 'swing_details': {"message": "Not enough pivots to identify a swing."}}

        last_pivot = pivots_df.iloc[-1]
        prev_pivot = pivots_df.iloc[-2]
        start_price = prev_pivot[price_col]
        end_price = last_pivot[price_col]
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

        # --- 3. Calculate Fibonacci Levels ---
        levels = []
        for level in self.retracement_levels:
            price = end_price - (price_diff * (level / 100.0))
            levels.append({"level": f"{level}%", "price": round(price, 5), "type": "Retracement"})
        for level in self.extension_levels:
            price = end_price + (price_diff * ((level - 100) / 100.0))
            levels.append({"level": f"{level}%", "price": round(price, 5), "type": "Extension"})
        
        # --- 4. Analyze current price position (Bias-Free) ---
        if len(self.df) < 2: return {"status": "Insufficient Data"}
        current_price = self.df.iloc[-2]['close']
        
        position = "Outside Retracement Zone"
        in_golden_zone = False
        retracement_levels = [lvl for lvl in levels if lvl['type'] == 'Retracement']
        sorted_levels = sorted(retracement_levels, key=lambda x: x['price'], reverse=(swing_trend == "Up"))
        
        for i in range(len(sorted_levels) - 1):
            upper_level, lower_level = sorted_levels[i], sorted_levels[i+1]
            if min(lower_level['price'], upper_level['price']) <= current_price <= max(lower_level['price'], upper_level['price']):
                position = f"Between {lower_level['level']} and {upper_level['level']}"
                if self.golden_zone_levels.issubset({level.replace('%','') for level in [lower_level['level'], upper_level['level']]}):
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
