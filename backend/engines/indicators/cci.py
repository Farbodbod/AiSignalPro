# backend/engines/indicators/cci.py (v5.1 - The Master Analyst Edition)
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class CciIndicator(BaseIndicator):
    """
    CCI Indicator - (v5.1 - The Master Analyst Edition)
    --------------------------------------------------------------------------
    This world-class version evolves the indicator into a master analyst. It
    introduces 'Exit Zone' signals, granular signal strength analysis, and the
    detection of 'Extreme' market conditions, providing unparalleled insight
    into momentum behavior for our advanced strategies.
    """
    dependencies: list = []

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.period = int(self.params.get('period', 20))
        self.constant = float(self.params.get('constant', 0.015))
        self.timeframe = self.params.get('timeframe', None)
        self.use_adaptive_thresholds = bool(self.params.get('use_adaptive_thresholds', True))
        self.adaptive_multiplier = float(self.params.get('adaptive_multiplier', 2.0))
        self.adaptive_min_level = float(self.params.get('adaptive_min_level', 100.0))
        self.fixed_overbought = float(self.params.get('overbought', 100.0))
        self.fixed_oversold = float(self.params.get('oversold', -100.0))
        self.extreme_overbought = float(self.params.get('extreme_overbought', 200.0))
        self.extreme_oversold = float(self.params.get('extreme_oversold', -200.0))
        
        suffix = f'_{self.period}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        else: suffix += '_base'
        self.cci_col = f'cci{suffix}'

    def calculate(self) -> 'CciIndicator':
        if len(self.df) < self.period:
            logger.warning(f"Not enough data for CCI on {self.timeframe or 'base'}.")
            self.df[self.cci_col] = np.nan
            return self

        tp = (self.df['high'] + self.df['low'] + self.df['close']) / 3
        ma_tp = tp.rolling(window=self.period).mean()
        mean_dev = tp.rolling(window=self.period).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
        
        safe_denominator = (self.constant * mean_dev).replace(0, np.nan)
        cci_series = (tp - ma_tp) / safe_denominator
        
        self.df[self.cci_col] = cci_series.ffill(limit=3).bfill(limit=2)
        return self

    def analyze(self) -> Dict[str, Any]:
        empty_analysis = {"values": {}, "analysis": {}, "thresholds": {}}
        if self.cci_col not in self.df.columns or self.df[self.cci_col].isnull().all():
            return {"status": "Calculation Incomplete", **empty_analysis}

        valid_cci = self.df[self.cci_col].dropna()
        if len(valid_cci) < 2:
            return {"status": "Insufficient Data", **empty_analysis}
        
        last_val, prev_val = valid_cci.iloc[-1], valid_cci.iloc[-2]
        
        if self.use_adaptive_thresholds:
            cci_std = valid_cci.std()
            overbought_level = max(cci_std * self.adaptive_multiplier, self.adaptive_min_level)
            oversold_level = -overbought_level
            threshold_type = "Adaptive"
        else:
            overbought_level = self.fixed_overbought
            oversold_level = self.fixed_oversold
            threshold_type = "Fixed"

        position = "Neutral"
        if last_val > self.extreme_overbought: position = "Extreme Overbought"
        elif last_val < self.extreme_oversold: position = "Extreme Oversold"
        elif last_val > overbought_level: position = "Overbought"
        elif last_val < oversold_level: position = "Oversold"
        
        signal, strength = "Hold", "Neutral"
        # Crossover Signals
        if prev_val <= oversold_level and last_val > oversold_level:
            signal, strength = "Bullish Crossover", "Strong" if position == "Neutral" else "Weak"
        elif prev_val >= overbought_level and last_val < overbought_level:
            signal, strength = "Bearish Crossover", "Strong" if position == "Neutral" else "Weak"
        # Exit Zone Signals
        elif prev_val <= oversold_level and last_val > oversold_level:
             signal = "Exit Sell Zone"
        elif prev_val >= overbought_level and last_val < overbought_level:
             signal = "Exit Buy Zone"
        # Enter Zone Signals with Strength
        elif position == "Oversold":
             signal = "Enter Sell Zone"; strength = "Strong" if last_val < (oversold_level - 50) else "Weak"
        elif position == "Overbought":
             signal = "Enter Buy Zone"; strength = "Strong" if last_val > (overbought_level + 50) else "Weak"

        values_content = {"cci": round(last_val, 2)}
        analysis_content = {"position": position, "signal": signal, "strength": strength}
        thresholds_content = {
            "type": threshold_type,
            "overbought": round(overbought_level, 2),
            "oversold": round(oversold_level, 2),
            "extreme_overbought": self.extreme_overbought,
            "extreme_oversold": self.extreme_oversold
        }

        return {
            "status": "OK",
            "timeframe": self.timeframe or "Base",
            "values": values_content,
            "analysis": analysis_content,
            "thresholds": thresholds_content
        }
