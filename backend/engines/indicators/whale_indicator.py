# backend/engines/indicators/whale_indicator.py (v6.1 - The Grandmaster Polish)
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Optional

from .base import BaseIndicator
from .utils import get_indicator_config_key

logger = logging.getLogger(__name__)

class WhaleIndicator(BaseIndicator):
    """
    Whale Activity Detector - (v6.1 - The Grandmaster Polish)
    ------------------------------------------------------------------------------------
    This world-class version incorporates final polishing touches for institutional-
    grade quality. It caps the quantum score at 100 for data integrity and
    introduces smart, context-aware summary messages for unparalleled analytical
    clarity. It is the definitive version of this indicator.
    """
    dependencies: list = ['atr']

    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], **kwargs):
        super().__init__(df, params=params, **kwargs)
        self.period = int(self.params.get('period', 20))
        self.stdev_multiplier = float(self.params.get('stdev_multiplier', 2.5))
        self.climactic_multiplier = float(self.params.get('climactic_multiplier', 4.0)) 
        self.timeframe = self.params.get('timeframe')

        suffix = f'_{self.period}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        else: suffix += '_base'
        self.vol_ma_col = f'vol_ma{suffix}'
        self.vol_std_col = f'vol_std{suffix}'
        
        self.atr_instance: Optional[BaseIndicator] = None
        self.atr_col_name: Optional[str] = None

    def calculate(self) -> 'WhaleIndicator':
        my_deps_config = self.params.get("dependencies", {})
        atr_order_params = my_deps_config.get('atr')
        if atr_order_params:
            atr_unique_key = get_indicator_config_key('atr', atr_order_params)
            self.atr_instance = self.dependencies.get(atr_unique_key)
            if self.atr_instance and hasattr(self.atr_instance, 'atr_col'):
                self.atr_col_name = self.atr_instance.atr_col
                if self.atr_col_name in self.atr_instance.df.columns:
                    self.df = self.df.join(self.atr_instance.df[[self.atr_col_name]], how='left')

        if len(self.df) < self.period:
            logger.warning(f"Not enough data for Whale Indicator on {self.timeframe or 'base'}.")
            self.df[self.vol_ma_col] = np.nan; self.df[self.vol_std_col] = np.nan
            return self

        min_p = max(2, self.period // 2)
        self.df[self.vol_ma_col] = self.df['volume'].rolling(window=self.period, min_periods=min_p).mean()
        self.df[self.vol_std_col] = self.df['volume'].rolling(window=self.period, min_periods=min_p).std(ddof=0)
        return self

    def analyze(self) -> Dict[str, Any]:
        required_cols = [self.vol_ma_col, self.vol_std_col, 'close', 'open', 'high', 'low', 'volume']
        empty_analysis = {"values": {}, "analysis": {}}
        if not all(col in self.df.columns for col in required_cols):
            return {"status": "Calculation Incomplete", **empty_analysis}

        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 1: return {"status": "Insufficient Data", **empty_analysis}

        last_candle = valid_df.iloc[-1]
        last_volume, avg_volume, std_volume = last_candle['volume'], last_candle[self.vol_ma_col], last_candle[self.vol_std_col]
        
        whale_threshold = avg_volume + (std_volume * self.stdev_multiplier)
        climactic_threshold = avg_volume + (std_volume * self.climactic_multiplier)
        
        is_whale_activity = last_volume > whale_threshold
        is_climactic_volume = last_volume > climactic_threshold
        
        spike_score = (last_volume - avg_volume) / std_volume if std_volume > 1e-9 else 0
        
        pressure, body_ratio = "Neutral", 0.0
        candle_range = last_candle['high'] - last_candle['low']
        if candle_range > 1e-9:
            body_ratio = abs(last_candle['close'] - last_candle['open']) / candle_range
        
        if is_whale_activity:
            if last_candle['close'] > last_candle['open']: pressure = "Buying Pressure"
            elif last_candle['close'] < last_candle['open']: pressure = "Selling Pressure"
            else: pressure = "Indecisive"
        
        whale_score = 0
        if is_whale_activity:
            spike_points = min(spike_score, 5.0) * 10 
            body_points = body_ratio * 30
            atr_points = 0
            if self.atr_col_name and self.atr_col_name in last_candle and pd.notna(last_candle[self.atr_col_name]):
                atr_val = last_candle[self.atr_col_name]
                if atr_val > 1e-9:
                    atr_ratio = candle_range / atr_val
                    atr_points = min(atr_ratio, 2.0) * 10
            # ✅ DATA INTEGRITY FIX: Cap the whale_score at 100.
            whale_score = min(100, int(spike_points + body_points + atr_points))

        # ✅ SMART SUMMARY (v6.1): Generate context-aware summary messages.
        summary = "Normal Activity"
        if is_climactic_volume:
            summary = "Climactic Buying" if pressure == "Buying Pressure" else "Climactic Selling" if pressure == "Selling Pressure" else "Climactic Volume"
        elif is_whale_activity:
            summary = f"Whale Activity ({'Bullish' if pressure == 'Buying Pressure' else 'Bearish' if pressure == 'Selling Pressure' else 'Neutral'})"

        values_content = {
            "last_volume": last_volume, "avg_volume": round(avg_volume, 2),
            "whale_threshold": round(whale_threshold, 2), "climax_threshold": round(climactic_threshold, 2),
        }
        analysis_content = {
            "is_whale_activity": is_whale_activity, "is_climactic_volume": is_climactic_volume,
            "spike_score": round(spike_score, 2), "whale_score": whale_score,
            "pressure": pressure, "candle_body_ratio": round(body_ratio, 2),
            "summary": summary
        }

        return {
            "status": "OK", "timeframe": self.timeframe or 'Base',
            "values": values_content, "analysis": analysis_content
        }
