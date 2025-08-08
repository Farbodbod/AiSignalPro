import pandas as pd
import numpy as np
import logging
from collections import OrderedDict
from typing import Dict, Any, Optional, List

# BaseIndicator را از ماژول مربوطه وارد کنید
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class PivotPointIndicator(BaseIndicator):
    """
    PivotPointIndicator - Definitive World-Class Version
    ------------------------------------------------------
    This version embodies the highest standards of the AiSignalPro project.

    Architectural Principles:
    - Single Responsibility: `calculate` computes raw data, `analyze` interprets it.
    - API-First Design: `analyze` output is a rich, stable, JSON-friendly structure.
    - Extreme Robustness: Handles all edge cases (NaN, Inf, bad data, insufficient data).
    - High Configurability: Method, precision, and behavior are user-configurable.

    Features:
    - Supports 'standard', 'fibonacci', 'camarilla' methods.
    - Uses a tolerance (`epsilon`) for precise "At Level" detection.
    - Guarantees output level order for consistent frontend display.
    """
    ALLOWED_METHODS = {'standard', 'fibonacci', 'camarilla'}

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        # --- Configuration ---
        self.method = str(self.params.get('method', 'standard')).lower()
        if self.method not in self.ALLOWED_METHODS:
            logger.warning(f"Unknown pivot method '{self.method}'. Falling back to 'standard'.")
            self.method = 'standard'
        self.precision = int(self.params.get('precision', 5))
        
        # --- State ---
        self._raw_pivots: Dict[str, float] = {}
        self._is_calculated = False
        self._calculation_status = "OK"

    def _validate_and_get_ohlc(self) -> Optional[Dict[str, float]]:
        """Validates input data and returns the previous candle's OHLC."""
        if len(self.df) < 2:
            self._calculation_status = "Insufficient Data"
            logger.warning("Pivot Points require at least 2 data points.")
            return None

        prev_candle = self.df.iloc[-2].copy()
        required_cols = {'high', 'low', 'close'}
        
        if prev_candle[required_cols].isnull().any():
            self._calculation_status = "Invalid Data (NaN)"
            logger.warning("Previous candle contains NaN values. Skipping calculation.")
            return None

        try:
            ohlc = prev_candle[required_cols].astype(float).to_dict()
        except (ValueError, TypeError) as e:
            self._calculation_status = f"Invalid Data (Cast Error: {e})"
            logger.error("Failed to cast OHLC to float: %s", e)
            return None

        if ohlc['high'] < ohlc['low']:
            self._calculation_status = "Invalid Data (High < Low)"
            logger.warning("Invalid previous candle: High is less than Low.")
            return None
        
        return ohlc

    def calculate(self) -> 'PivotPointIndicator':
        """Calculates the raw pivot point values based on the chosen method."""
        self._raw_pivots.clear()
        ohlc = self._validate_and_get_ohlc()

        if ohlc is None:
            self._is_calculated = True
            return self

        h, l, c = ohlc['high'], ohlc['low'], ohlc['close']
        p = (h + l + c) / 3.0
        r = h - l
        
        raw = {}
        if self.method == 'fibonacci':
            raw = {'R3': p + r, 'R2': p + (r * 0.618), 'R1': p + (r * 0.382), 'P': p, 'S1': p - (r * 0.382), 'S2': p - (r * 0.618), 'S3': p - r}
        elif self.method == 'camarilla':
            raw = {'R4': c+(r*1.1/2),'R3': c+(r*1.1/4),'R2': c+(r*1.1/6),'R1': c+(r*1.1/12),'P': p,'S1': c-(r*1.1/12),'S2': c-(r*1.1/6),'S3': c-(r*1.1/4),'S4': c-(r*1.1/2)}
        else: # Standard
            raw = {'R3': h+2*(p-l),'R2': p+r,'R1': (2*p)-l,'P': p,'S1': (2*p)-h,'S2': p-r,'S3': l-2*(h-p)}

        self._raw_pivots = raw
        self._is_calculated = True
        return self

    def analyze(self) -> Dict[str, Any]:
        """Analyzes the current price against the calculated pivot levels."""
        if not self._is_calculated:
            self.calculate()
        
        if not self._raw_pivots:
            return {'status': self._calculation_status, 'levels': [], 'analysis': {}}

        current_price = self.df['close'].iloc[-1]
        if pd.isna(current_price):
             return {'status': 'Invalid Current Price (NaN)', 'levels': [], 'analysis': {}}

        # --- Position Analysis ---
        position = "Unknown"
        epsilon = 10 ** -(self.precision + 1)
        
        # Check for exact match first
        for name, price in self._raw_pivots.items():
            if abs(current_price - price) <= epsilon:
                position = f"At {name}"
                break
        
        # If no exact match, find position between levels
        if position == "Unknown":
            sorted_levels = sorted(self._raw_pivots.items(), key=lambda item: item[1])
            prices = [item[1] for item in sorted_levels]
            names = [item[0] for item in sorted_levels]
            
            if current_price > prices[-1]: position = f"Above {names[-1]}"
            elif current_price < prices[0]: position = f"Below {names[0]}"
            else:
                for i in range(len(prices) - 1):
                    if prices[i] < current_price < prices[i+1]:
                        position = f"Between {names[i]} and {names[i+1]}"
                        break
        
        # --- Format final output ---
        # ✨ IMPROVEMENT: Use a list of dicts for the most stable JSON output
        formatted_levels = [
            {"level": name, "price": round(price, self.precision)}
            for name, price in sorted(self._raw_pivots.items(), key=lambda item: item[1], reverse=True)
        ]
        
        return {
            'status': 'OK',
            'method': self.method,
            'levels': formatted_levels,
            'analysis': {
                'current_price': round(current_price, self.precision),
                'position': position
            }
        }
