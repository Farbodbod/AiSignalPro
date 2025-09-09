# backend/engines/indicators/divergence_indicator.py (v8.0 - The Precision Engine)
import pandas as pd
import logging
from typing import Dict, Any, Optional

from .base import BaseIndicator
from .utils import get_indicator_config_key

logger = logging.getLogger(__name__)

class DivergenceIndicator(BaseIndicator):
    """
    Divergence Engine - (v8.0 - The Precision Engine)
    -----------------------------------------------------------------------------------
    This version enhances the analytical output to provide maximum precision for
    advanced strategies. It now includes separate, explicit boolean flags for
    Regular and Hidden divergences, allowing strategies to distinguish between
    reversal and continuation signals with flawless accuracy. All functionalities
    from v7.0 are preserved.
    """
    default_config: Dict[str, Any] = {
        'lookback_pivots': 5,
        'min_bar_distance': 5,
        'dependencies': {
            'rsi': {'period': 14},
            'zigzag': {'deviation': 3.0}
        }
    }

    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], **kwargs):
        super().__init__(df, params=params, **kwargs)
        self.timeframe = self.params.get('timeframe')
        self.lookback_pivots = int(self.params.get('lookback_pivots', self.default_config['lookback_pivots']))
        self.min_bar_distance = int(self.params.get('min_bar_distance', self.default_config['min_bar_distance']))
        self.unique_key = get_indicator_config_key('divergence', self.params)
        self.rsi_col: Optional[str] = None
        self.pivots_col: Optional[str] = None
        self.prices_col: Optional[str] = None

    def calculate(self) -> 'DivergenceIndicator':
        my_deps_config = self.params.get("dependencies", self.default_config['dependencies'])
        rsi_order_params = my_deps_config.get('rsi'); zigzag_order_params = my_deps_config.get('zigzag')
        if not rsi_order_params or not zigzag_order_params:
            logger.error(f"[{self.unique_key}] on {self.timeframe}: RSI or ZigZag dependency not defined."); return self
        
        rsi_unique_key = get_indicator_config_key('rsi', rsi_order_params); zigzag_unique_key = get_indicator_config_key('zigzag', zigzag_order_params)
        rsi_instance = self.dependencies.get(rsi_unique_key); zigzag_instance = self.dependencies.get(zigzag_unique_key)
        
        if not isinstance(rsi_instance, BaseIndicator) or not isinstance(zigzag_instance, BaseIndicator):
            logger.warning(f"[{self.unique_key}] on {self.timeframe}: missing critical dependencies."); return self

        self.rsi_col = getattr(rsi_instance, 'rsi_col', None); self.pivots_col = getattr(zigzag_instance, 'pivots_col', None); self.prices_col = getattr(zigzag_instance, 'prices_col', None)
        if not all([self.rsi_col, self.pivots_col, self.prices_col]):
            logger.warning(f"[{self.unique_key}] on {self.timeframe}: could not find required columns in dependencies."); return self
        
        self.df[f"RSI_for_{self.unique_key}"] = rsi_instance.df[self.rsi_col]; self.df[f"PIVOTS_for_{self.unique_key}"] = zigzag_instance.df[self.pivots_col]; self.df[f"PRICES_for_{self.unique_key}"] = zigzag_instance.df[self.prices_col]
        self.rsi_col, self.pivots_col, self.prices_col = f"RSI_for_{self.unique_key}", f"PIVOTS_for_{self.unique_key}", f"PRICES_for_{self.unique_key}"
        return self

    def analyze(self) -> Dict[str, Any]:
        empty_analysis = {"signals": [], "has_bullish_divergence": False, "has_bearish_divergence": False, "has_hidden_bullish_divergence": False, "has_hidden_bearish_divergence": False, "has_regular_bullish_divergence": False, "has_regular_bearish_divergence": False}
        required_cols = [self.rsi_col, self.pivots_col, self.prices_col]
        if not all(col in self.df.columns for col in required_cols):
            return {"status": "Calculation Incomplete", "values": {}, "analysis": empty_analysis}

        pivots_df = self.df.dropna(subset=required_cols)
        pivots_df = pivots_df[pivots_df[self.pivots_col] != 0]

        if len(pivots_df) < 2:
            return {"status": "OK", "timeframe": self.timeframe or 'Base', "values": {}, "analysis": empty_analysis}
            
        signals = []
        # ✅ UPGRADE: Precise boolean flags for each divergence type
        flags = {"regular_bullish": False, "hidden_bullish": False, "regular_bearish": False, "hidden_bearish": False}
        
        recent_pivots = pivots_df.tail(self.lookback_pivots)
        for i in range(len(recent_pivots)):
            for j in range(i + 1, len(recent_pivots)):
                pivot1, pivot2 = recent_pivots.iloc[i], recent_pivots.iloc[j]
                bar_distance = self.df.index.get_loc(pivot2.name) - self.df.index.get_loc(pivot1.name)
                if bar_distance < self.min_bar_distance: continue

                price1, rsi1 = pivot1[self.prices_col], pivot1[self.rsi_col]; price2, rsi2 = pivot2[self.prices_col], pivot2[self.rsi_col]
                divergence_type, flag_key = None, None
                
                if pivot1[self.pivots_col] == 1 and pivot2[self.pivots_col] == 1: # Peaks
                    if price2 > price1 and rsi2 < rsi1: divergence_type, flag_key = "Regular Bearish", "regular_bearish"
                    elif price2 < price1 and rsi2 > rsi1: divergence_type, flag_key = "Hidden Bearish", "hidden_bearish"
                elif pivot1[self.pivots_col] == -1 and pivot2[self.pivots_col] == -1: # Troughs
                    if price2 < price1 and rsi2 > rsi1: divergence_type, flag_key = "Regular Bullish", "regular_bullish"
                    elif price2 > price1 and rsi2 < rsi1: divergence_type, flag_key = "Hidden Bullish", "hidden_bullish"

                if divergence_type:
                    signals.append({"type": divergence_type, "pivots": [{"time": str(pivot1.name), "price": round(price1, 5), "oscillator_value": round(rsi1, 2)}, {"time": str(pivot2.name), "price": round(price2, 5), "oscillator_value": round(rsi2, 2)}]})
                    if flag_key: flags[flag_key] = True
        
        analysis_content = {
            "signals": signals,
            # ✅ UPGRADE: Specific flags for precise strategic use
            "has_regular_bullish_divergence": flags["regular_bullish"],
            "has_regular_bearish_divergence": flags["regular_bearish"],
            "has_hidden_bullish_divergence": flags["hidden_bullish"],
            "has_hidden_bearish_divergence": flags["hidden_bearish"],
            # General flags for backward compatibility
            "has_bullish_divergence": flags["regular_bullish"] or flags["hidden_bullish"],
            "has_bearish_divergence": flags["regular_bearish"] or flags["hidden_bearish"],
        }
        
        return {"status": "OK", "timeframe": self.timeframe or 'Base', "values": {}, "analysis": analysis_content}

