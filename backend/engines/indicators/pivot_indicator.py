import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Optional, List

# اطمینان حاصل کنید که این اندیکاتورها از فایل‌های مربوطه و در نسخه‌های نهایی خود وارد شده‌اند
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class PivotPointIndicator(BaseIndicator):
    """
    PivotPointIndicator - Definitive, Complete, MTF & World-Class Version
    ----------------------------------------------------------------------
    This is the final, unified version combining multiple calculation methods,
    intelligent analysis, and the multi-timeframe (MTF) architectural pattern.
    It calculates pivots based on a higher timeframe (e.g., Daily, Weekly)
    for use on a lower timeframe chart.
    """
    ALLOWED_METHODS = {'standard', 'fibonacci', 'camarilla'}

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        # --- Parameters ---
        self.params = kwargs.get('params', {})
        self.method = str(self.params.get('method', 'standard')).lower()
        if self.method not in self.ALLOWED_METHODS:
            logger.warning(f"Unknown pivot method '{self.method}'. Falling back to 'standard'.")
            self.method = 'standard'
        
        self.timeframe = self.params.get('timeframe', None) # e.g., 'D' for Daily, 'W' for Weekly
        self.precision = int(self.params.get('precision', 5))
        
        # --- State ---
        self._raw_pivots: Dict[str, float] = {}
        self._is_calculated = False
        self._calculation_status = "Not Calculated"

    def _get_previous_period_ohlc(self) -> Optional[Dict[str, float]]:
        """
        Gets the OHLC of the correct previous period.
        If MTF, it resamples to get the last complete higher-timeframe candle.
        If not MTF, it simply takes the previous candle from the current timeframe.
        """
        if self.timeframe:
            if not isinstance(self.df.index, pd.DatetimeIndex):
                raise TypeError("DataFrame index must be a DatetimeIndex for MTF pivot calculation.")
            
            # Resample to get the history of the higher timeframe
            rules = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}
            htf_df = self.df.resample(self.timeframe).apply(rules).dropna()
            
            if len(htf_df) < 2:
                self._calculation_status = f"Insufficient Data for timeframe '{self.timeframe}'"
                return None
            
            # The "previous period" is the second to last candle of the resampled data
            prev_period_ohlc = htf_df.iloc[-2]
        else:
            if len(self.df) < 2:
                self._calculation_status = "Insufficient Data (less than 2 bars)"
                return None
            # The "previous period" is simply the previous candle
            prev_period_ohlc = self.df.iloc[-2]

        # --- Validation of the final chosen candle ---
        required_cols = {'high', 'low', 'close'}
        if prev_period_ohlc[required_cols].isnull().any():
            self._calculation_status = "Invalid Data (NaN in OHLC)"
            return None
        
        ohlc = prev_period_ohlc[required_cols].astype(float).to_dict()
        if ohlc['high'] < ohlc['low']:
            self._calculation_status = "Invalid Data (High < Low)"
            return None
            
        return ohlc

    def calculate(self) -> 'PivotPointIndicator':
        """Calculates the raw pivot point values based on the chosen method and timeframe."""
        self._raw_pivots.clear()
        ohlc = self._get_previous_period_ohlc()

        if ohlc is None:
            self._is_calculated = True
            return self

        h, l, c = ohlc['high'], ohlc['low'], ohlc['close']
        p = (h + l + c) / 3.0
        
        raw = {}
        if self.method == 'fibonacci':
            r = h - l
            raw = {'R3': p+r, 'R2': p+(r*0.618), 'R1': p+(r*0.382), 'P': p, 'S1': p-(r*0.382), 'S2': p-(r*0.618), 'S3': p-r}
        elif self.method == 'camarilla':
            r = h - l
            raw = {'R4': c+(r*1.1/2), 'R3': c+(r*1.1/4), 'R2': c+(r*1.1/6), 'R1': c+(r*1.1/12), 'P': p, 'S1': c-(r*1.1/12), 'S2': c-(r*1.1/6), 'S3': c-(r*1.1/4), 'S4': c-(r*1.1/2)}
        else: # Standard
            raw = {'R3': h+2*(p-l), 'R2': p+(h-l), 'R1': (2*p)-l, 'P': p, 'S1': (2*p)-h, 'S2': p-(h-l), 'S3': l-2*(h-p)}

        self._raw_pivots = raw
        self._calculation_status = "OK"
        self._is_calculated = True
        return self

    def analyze(self) -> Dict[str, Any]:
        """Analyzes the current price against the calculated pivot levels."""
        if not self._is_calculated: self.calculate()
        
        if not self._raw_pivots:
            return {'status': self._calculation_status, 'levels': [], 'analysis': {}}

        current_price = self.df['close'].iloc[-1]
        if pd.isna(current_price):
            return {'status': 'Invalid Current Price (NaN)', 'levels': [], 'analysis': {}}

        # --- Position Analysis with Epsilon Tolerance ---
        position = "Unknown"
        epsilon = 10 ** -(self.precision + 1)
        
        for name, price in self._raw_pivots.items():
            if abs(current_price - price) <= epsilon: position = f"At {name}"; break
        
        if position == "Unknown":
            sorted_levels = sorted(self._raw_pivots.items(), key=lambda item: item[1])
            prices = [item[1] for item in sorted_levels]
            names = [item[0] for item in sorted_levels]
            if current_price > prices[-1]: position = f"Above {names[-1]}"
            elif current_price < prices[0]: position = f"Below {names[0]}"
            else:
                for i in range(len(prices) - 1):
                    if prices[i] < current_price < prices[i+1]:
                        position = f"Between {names[i]} and {names[i+1]}"; break
        
        # --- Format Final Output ---
        formatted_levels = [
            {"level": name, "price": round(price, self.precision)}
            for name, price in sorted(self._raw_pivots.items(), key=lambda item: item[1], reverse=True)
        ]
        
        return {
            'status': self._calculation_status,
            'method': self.method,
            'timeframe': self.timeframe or 'Previous Candle',
            'levels': formatted_levels,
            'analysis': {
                'current_price': round(current_price, self.precision),
                'position': position
            }
        }
