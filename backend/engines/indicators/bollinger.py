# backend/engines/indicators/bollinger.py (v6.1 - The Final Standard Edition)

import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Optional

from .base import BaseIndicator
from .utils import get_indicator_config_key

logger = logging.getLogger(__name__)

class BollingerIndicator(BaseIndicator):
    """
    Bollinger Bands - (v6.1 - The Final Standard Edition)
    -----------------------------------------------------------------------------
    This world-class version is fully aligned with all final architectural standards.
    It fixes a critical AttributeError by using proper dependency injection for the
    'whales' indicator. It also features dynamic column naming for multi-instance
    safety and a fully Sentinel-compliant output structure.
    """
    dependencies: list = ['whales'] # Formal dependency declaration

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.period = int(self.params.get('period', 20))
        self.std_dev = float(self.params.get('std_dev', 2.0))
        self.timeframe = self.params.get('timeframe', None)
        self.squeeze_stats_period = int(self.params.get('squeeze_stats_period', 240))
        self.squeeze_std_multiplier = float(self.params.get('squeeze_std_multiplier', 1.5))

        # ✅ FINAL STANDARD: Dynamic and conflict-proof column naming.
        suffix = f'_{self.period}_{self.std_dev}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        else: suffix += '_base'
        
        self.middle_col = f'bb_middle{suffix}'
        self.upper_col = f'bb_upper{suffix}'
        self.lower_col = f'bb_lower{suffix}'
        self.width_col = f'bb_width{suffix}'
        self.percent_b_col = f'bb_percent_b{suffix}'
        
        self.whales_instance: Optional[BaseIndicator] = None

    def calculate(self) -> 'BollingerIndicator':
        if len(self.df) < self.period:
            logger.warning(f"Not enough data for Bollinger Bands on {self.timeframe or 'base'}.")
            for col in [self.middle_col, self.upper_col, self.lower_col, self.width_col, self.percent_b_col]:
                self.df[col] = np.nan
            return self

        # ✅ DEPENDENCY INJECTION: Look up the whales instance once during calculation.
        whales_unique_key = get_indicator_config_key('whales', self.params.get('dependencies', {}).get('whales', {}))
        self.whales_instance = self.dependencies.get(whales_unique_key)

        middle = self.df['close'].rolling(window=self.period).mean()
        std = self.df['close'].rolling(window=self.period).std(ddof=0)
        
        upper = middle + (std * self.std_dev)
        lower = middle - (std * self.std_dev)
        
        safe_middle = middle.replace(0, np.nan)
        width = (upper - lower) / safe_middle * 100
        percent_b = (self.df['close'] - lower) / (upper - lower).replace(0, np.nan)
        
        self.df[self.middle_col] = middle.ffill(limit=3).bfill(limit=2)
        self.df[self.upper_col] = upper.ffill(limit=3).bfill(limit=2)
        self.df[self.lower_col] = lower.ffill(limit=3).bfill(limit=2)
        self.df[self.width_col] = width.ffill(limit=3).bfill(limit=2)
        self.df[self.percent_b_col] = percent_b.ffill(limit=3).bfill(limit=2)
        return self

    def analyze(self) -> Dict[str, Any]:
        required_cols = [self.middle_col, self.upper_col, self.lower_col, self.width_col, self.percent_b_col]
        empty_analysis = {"values": {}, "analysis": {}}
        if not all(col in self.df.columns for col in required_cols):
            return {"status": "Calculation Incomplete", **empty_analysis}

        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < self.squeeze_stats_period:
            return {"status": "Insufficient Data for Squeeze Analysis", **empty_analysis}

        last = valid_df.iloc[-1]; prev = valid_df.iloc[-2]
        
        width_history = valid_df[self.width_col].tail(self.squeeze_stats_period)
        width_mean, width_std = width_history.mean(), width_history.std()
        dynamic_squeeze_threshold = width_mean - (width_std * self.squeeze_std_multiplier)
        is_squeeze_now = last[self.width_col] <= dynamic_squeeze_threshold
        is_squeeze_prev = prev[self.width_col] <= dynamic_squeeze_threshold
        is_squeeze_release = is_squeeze_prev and not is_squeeze_now
        
        position = "Inside Bands"
        if last[self.percent_b_col] > 1.0: position = "Breakout Above"
        elif last[self.percent_b_col] < 0.0: position = "Breakdown Below"
        
        prev_position = "Inside Bands"
        if prev[self.percent_b_col] > 1.0: prev_position = "Breakout Above"
        elif prev[self.percent_b_col] < 0.0: prev_position = "Breakdown Below"

        trade_signal, strength = "Hold", "Neutral"
        short_term_trend = "Bullish" if last['close'] > last[self.middle_col] else "Bearish"

        # ✅ ARCHITECTURE FIX: Use the injected dependency instance.
        volume_spike = False
        if self.whales_instance:
            whales_analysis = self.whales_instance.analyze()
            volume_spike = (whales_analysis.get('analysis') or {}).get('is_whale_activity', False)

        if is_squeeze_release:
            strength = "Strong" if volume_spike else "Weak"
            if short_term_trend == "Bullish": trade_signal = f"Squeeze Release Bullish"
            else: trade_signal = f"Squeeze Release Bearish"
        elif is_squeeze_now:
            trade_signal = "Squeeze Active"
        elif position != "Inside Bands" and prev_position == "Inside Bands":
             trade_signal = position
        elif position == "Inside Bands" and prev_position != "Inside Bands":
             trade_signal = "Exit Breakout"
        elif position != "Inside Bands":
             trade_signal = "Breakout Continuation"

        values_content = {
            "upper_band": round(last[self.upper_col], 5), "middle_band": round(last[self.middle_col], 5),
            "lower_band": round(last[self.lower_col], 5), "bandwidth_percent": round(last[self.width_col], 4),
            "percent_b": round(last[self.percent_b_col], 3),
        }
        analysis_content = {
            "trade_signal": trade_signal, "strength": strength,
            "is_in_squeeze": is_squeeze_now, "is_squeeze_release": is_squeeze_release,
            "position": position, "short_term_trend": short_term_trend,
            "dynamic_squeeze_threshold": round(dynamic_squeeze_threshold, 4)
        }

        return {
            "status": "OK", "timeframe": self.timeframe or 'Base',
            "values": values_content, "analysis": analysis_content
        }
