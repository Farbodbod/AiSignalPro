# backend/engines/indicators/pivot_indicator.py (v5.1 - The Final Hotfix)
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, List

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class PivotPointIndicator(BaseIndicator):
    """
    Pivot Points - (v5.1 - The Final Hotfix)
    -------------------------------------------------------------------------
    This world-class version contains the final architectural hotfix. The 'levels'
    output is now promoted to the root level of the analysis package, aligning it
    with the final data architecture of the project and ensuring system-wide
    accessibility. All previous features from v5.0 are 100% preserved.
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
        
        self.reset_period = self.params.get('reset_period', '1D')
        self.timeframe = self.params.get('timeframe')
        self.precision = int(self.params.get('precision', 5))
        
        self.pivot_columns: List[str] = []

    def calculate(self) -> 'PivotPointIndicator':
        # ... [This method is unchanged and correct] ...
        if len(self.df) < 2:
            logger.warning(f"Not enough data for Pivot Point calculation on {self.timeframe}.")
            return self

        try:
            resampled_df = self.df.resample(self.reset_period).agg({
                'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'
            }).dropna()
        except Exception as e:
            logger.error(f"Failed to resample data for Pivots with reset_period '{self.reset_period}': {e}")
            return self

        if len(resampled_df) < 2:
            logger.warning(f"Not enough resampled data for Pivots with reset_period '{self.reset_period}'.")
            return self

        prev_candle = resampled_df.iloc[-2]
        h, l, c = prev_candle['high'], prev_candle['low'], prev_candle['close']
        p = (h + l + c) / 3.0
        
        pivots = {}
        if self.method == 'fibonacci':
            r = h - l; pivots = {'R3': p+r, 'R2': p+(r*0.618), 'R1': p+(r*0.382), 'P': p, 'S1': p-(r*0.382), 'S2': p-(r*0.618), 'S3': p-r}
        elif self.method == 'camarilla':
            r = h - l; pivots = {'R4': c+(r*1.1/2), 'R3': c+(r*1.1/4), 'R2': c+(r*1.1/6), 'R1': c+(r*1.1/12), 'P': p, 'S1': c-(r*1.1/12), 'S2': c-(r*1.1/6), 'S3': c-(r*1.1/4), 'S4': c-(r*1.1/2)}
        else: # Standard
            pivots = {'R3': h+2*(p-l), 'R2': p+(h-l), 'R1': (2*p)-l, 'P': p, 'S1': (2*p)-h, 'S2': p-(h-l), 'S3': l-2*(h-p)}

        self.pivot_columns = []
        for name, value in pivots.items():
            col_name = f"pivot_{self.method}_{self.reset_period}_{name.lower()}"
            self.df[col_name] = value; self.pivot_columns.append(col_name)

        return self

    def analyze(self) -> Dict[str, Any]:
        empty_analysis = {"values": {}, "analysis": {}}
        if not self.pivot_columns or any(col not in self.df.columns for col in self.pivot_columns):
            return {"status": "Calculation Incomplete", "levels": [], **empty_analysis}
        
        try:
            last_closed_candle = self.df.iloc[-1]; current_price = last_closed_candle['close']
        except IndexError:
             return {"status": "Insufficient Data", "levels": [], **empty_analysis}
        
        if pd.isna(current_price): return {'status': 'Invalid Current Price (NaN)', "levels": [], **empty_analysis}

        pivot_values = {col: last_closed_candle[col] for col in self.pivot_columns if pd.notna(last_closed_candle[col])}
        if not pivot_values: return {"status": "Pivot values are NaN", "levels": [], **empty_analysis}
            
        position = "In Range"; sorted_levels = sorted(pivot_values.items(), key=lambda item: item[1])
        
        for name, price in sorted_levels:
            if abs(current_price - price) / max(price, 1e-9) < 0.001:
                position = f"At {name.split('_')[-1].upper()}"; break
        
        if position == "In Range":
            prices = [item[1] for item in sorted_levels]; names = [item[0].split('_')[-1].upper() for item in sorted_levels]
            if current_price > prices[-1]: position = f"Above {names[-1]}"
            elif current_price < prices[0]: position = f"Below {names[0]}"
            else:
                for i in range(len(prices) - 1):
                    if prices[i] < current_price < prices[i+1]:
                        position = f"Between {names[i]} and {names[i+1]}"; break
        
        central_pivot_price = pivot_values.get(f"pivot_{self.method}_{self.reset_period}_p")
        bias = "Neutral"
        if central_pivot_price is not None:
            bias = "Bullish" if current_price > central_pivot_price else "Bearish"

        formatted_levels = [{"level": name.split('_')[-1].upper(), "price": round(price, self.precision)} for name, price in sorted(pivot_values.items(), key=lambda item: item[1], reverse=True)]
        
        values_content = {'levels': formatted_levels}
        analysis_content = {'current_price': round(current_price, self.precision), 'position': position, 'bias': bias}

        # ✅ THE FINAL HOTFIX (v5.1): Assemble the final dictionary with 'levels' at the root.
        return {
            'status': 'OK',
            'method': self.method,
            'reset_period': self.reset_period,
            'levels': formatted_levels,  # Promoted to the root level for system-wide access
            'values': values_content,    # Original structure preserved for compatibility
            'analysis': analysis_content
        }
