# backend/engines/indicators/whale_indicator.py
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class WhaleIndicator(BaseIndicator):
    """
    Whale Activity Detector - (v5.1 - Standardized & Hardened)
    ------------------------------------------------------------------------------------
    This world-class version is standardized to align with the latest project
    architecture, featuring a clean __init__ and simplified column names. Its
    powerful dual-threshold engine for differentiating "Whale Activity" from
    "Climactic Volume" remains 100% intact and is a key feature for advanced
    reversal and breakout strategies.
    """
    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], dependencies: Dict[str, BaseIndicator], **kwargs):
        super().__init__(df, params=params, dependencies=dependencies, **kwargs)
        self.period = int(self.params.get('period', 20))
        self.stdev_multiplier = float(self.params.get('stdev_multiplier', 2.5))
        self.climactic_multiplier = float(self.params.get('climactic_multiplier', 4.0)) 
        self.timeframe = self.params.get('timeframe')

        # Simplified, robust, and locally-scoped column names
        self.vol_ma_col = 'VOL_MA'
        self.vol_std_col = 'VOL_STD'

    def calculate(self) -> 'WhaleIndicator':
        """ Core calculation of volume moving average and standard deviation. """
        if len(self.df) < self.period:
            logger.warning(f"Not enough data for Whale Indicator on {self.timeframe or 'base'}.")
            self.df[self.vol_ma_col] = np.nan
            self.df[self.vol_std_col] = np.nan
            return self

        min_p = max(2, self.period // 2)
        self.df[self.vol_ma_col] = self.df['volume'].rolling(window=self.period, min_periods=min_p).mean()
        self.df[self.vol_std_col] = self.df['volume'].rolling(window=self.period, min_periods=min_p).std(ddof=0)

        return self

    def analyze(self) -> Dict[str, Any]:
        """ 
        Provides a deep, statistical analysis including climactic volume detection.
        The core logic of this method is 100% preserved.
        """
        required_cols = [self.vol_ma_col, self.vol_std_col, 'close', 'open', 'volume']
        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 1:
            return {"status": "Insufficient Data"}

        last_candle = valid_df.iloc[-1]
        
        last_volume = last_candle['volume']
        avg_volume = last_candle[self.vol_ma_col]
        std_volume = last_candle[self.vol_std_col]
        
        whale_threshold = avg_volume + (std_volume * self.stdev_multiplier)
        climactic_threshold = avg_volume + (std_volume * self.climactic_multiplier)
        
        is_whale_activity = last_volume > whale_threshold
        is_climactic_volume = last_volume > climactic_threshold
        
        spike_score = (last_volume - avg_volume) / std_volume if std_volume > 1e-9 else 0
        
        pressure = "Neutral"
        if is_whale_activity:
            if last_candle['close'] > last_candle['open']: pressure = "Buying Pressure"
            elif last_candle['close'] < last_candle['open']: pressure = "Selling Pressure"
            else: pressure = "Indecisive"

        summary = "Climactic Volume!" if is_climactic_volume else "Whale Activity" if is_whale_activity else "Normal Activity"

        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "values": {
                "last_volume": last_volume,
                "avg_volume": round(avg_volume, 2),
                "calculated_threshold_whale": round(whale_threshold, 2),
                "calculated_threshold_climax": round(climactic_threshold, 2),
            },
            "analysis": {
                "is_whale_activity": is_whale_activity,
                "is_climactic_volume": is_climactic_volume,
                "spike_score": round(spike_score, 2),
                "pressure": pressure,
                "summary": summary
            }
        }
