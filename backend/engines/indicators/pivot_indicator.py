import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, List

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class PivotPointIndicator(BaseIndicator):
    """
    Pivot Points - Definitive, World-Class Version (v4.0 - Final Architecture)
    -------------------------------------------------------------------------
    This version adheres to the final AiSignalPro architecture. It calculates
    pivot levels based on the pre-resampled dataframe provided by the
    IndicatorAnalyzer, making it a pure, efficient, and robust engine for
    identifying key mathematical levels.
    """
    dependencies: list = []
    ALLOWED_METHODS = {'standard', 'fibonacci', 'camarilla'}

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.method = str(self.params.get('method', 'standard')).lower()
        if self.method not in self.ALLOWED_METHODS:
            logger.warning(f"Unknown pivot method '{self.method}'. Falling back to 'standard'.")
            self.method = 'standard'
        
        # 'timeframe' here is used for column naming, but also represents the reset period
        self.timeframe = self.params.get('timeframe', 'D') 
        self.precision = int(self.params.get('precision', 5))
        
        # This will hold the calculated pivot names for easy access
        self.pivot_columns: List[str] = []

    def calculate(self) -> 'PivotPointIndicator':
        """
        ✨ FINAL ARCHITECTURE: No resampling. Just pure calculation.
        Calculates pivot levels based on the previous candle of the received dataframe.
        """
        df_for_calc = self.df
        
        if len(df_for_calc) < 2:
            logger.warning(f"Not enough data for Pivot Point calculation on timeframe {self.timeframe}.")
            return self

        prev_candle = df_for_calc.iloc[-2]
        h, l, c = prev_candle['high'], prev_candle['low'], prev_candle['close']

        if pd.isna(h) or pd.isna(l) or pd.isna(c) or h < l:
            logger.warning(f"Invalid previous candle data for Pivots on {self.timeframe}. Skipping.")
            return self

        p = (h + l + c) / 3.0
        
        pivots = {}
        if self.method == 'fibonacci':
            r = h - l
            pivots = {'R3': p+r, 'R2': p+(r*0.618), 'R1': p+(r*0.382), 'P': p, 'S1': p-(r*0.382), 'S2': p-(r*0.618), 'S3': p-r}
        elif self.method == 'camarilla':
            r = h - l
            pivots = {'R4': c+(r*1.1/2), 'R3': c+(r*1.1/4), 'R2': c+(r*1.1/6), 'R1': c+(r*1.1/12), 'P': p, 'S1': c-(r*1.1/12), 'S2': c-(r*1.1/6), 'S3': c-(r*1.1/4), 'S4': c-(r*1.1/2)}
        else: # Standard
            pivots = {'R3': h+2*(p-l), 'R2': p+(h-l), 'R1': (2*p)-l, 'P': p, 'S1': (2*p)-h, 'S2': p-(h-l), 'S3': l-2*(h-p)}

        # Add pivot levels as new columns to the dataframe
        self.pivot_columns = []
        for name, value in pivots.items():
            col_name = f"pivot_{name.lower()}_{self.timeframe}"
            self.df[col_name] = value
            self.pivot_columns.append(col_name)

        return self

    def analyze(self) -> Dict[str, Any]:
        """Analyzes the current price against the calculated pivot levels."""
        if not self.pivot_columns or any(col not in self.df.columns for col in self.pivot_columns):
            return {"status": "Not Calculated", "analysis": {}}

        # Bias-free analysis on the last closed candle
        if len(self.df) < 2: return {"status": "Insufficient Data"}
        last_closed_candle = self.df.iloc[-2]
        current_price = last_closed_candle['close']

        if pd.isna(current_price):
            return {'status': 'Invalid Current Price (NaN)'}

        # Extract pivot values from the last row
        pivot_values = {col: last_closed_candle[col] for col in self.pivot_columns}
        
        position = "In Range"
        epsilon = 10 ** -(self.precision + 1)
        
        sorted_levels = sorted(pivot_values.items(), key=lambda item: item[1])
        
        for name, price in sorted_levels:
            if abs(current_price - price) <= epsilon:
                position = f"At {name.split('_')[1].upper()}"; break
        
        if position == "In Range":
            prices = [item[1] for item in sorted_levels]
            names = [item[0].split('_')[1].upper() for item in sorted_levels]
            if current_price > prices[-1]: position = f"Above {names[-1]}"
            elif current_price < prices[0]: position = f"Below {names[0]}"
            else:
                for i in range(len(prices) - 1):
                    if prices[i] < current_price < prices[i+1]:
                        position = f"Between {names[i]} and {names[i+1]}"; break
        
        formatted_levels = [
            {"level": name.split('_')[1].upper(), "price": round(price, self.precision)}
            for name, price in sorted(pivot_values.items(), key=lambda item: item[1], reverse=True)
        ]
        
        return {
            'status': 'OK',
            'method': self.method,
            'reset_period': self.timeframe,
            'levels': formatted_levels,
            'analysis': {
                'current_price': round(current_price, self.precision),
                'position': position
            }
        }
