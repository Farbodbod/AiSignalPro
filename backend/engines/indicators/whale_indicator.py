import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class WhaleIndicator(BaseIndicator):
    """
    Whale Activity Detector - (v5.0 - Climax Detector)
    ------------------------------------------------------------------------------------
    This world-class version evolves beyond simple spike detection. It now features a
    dual-threshold system to differentiate between standard "Whale Activity" and a
    true, trend-ending "Climactic Volume" event, providing critical data for
    exhaustion-based reversal strategies.
    """
    dependencies: list = []

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.period = int(self.params.get('period', 20))
        self.stdev_multiplier = float(self.params.get('stdev_multiplier', 2.5)) # Standard whale activity
        # ✅ NEW: A much higher threshold for detecting a climax event
        self.climactic_multiplier = float(self.params.get('climactic_multiplier', 4.0)) 
        self.timeframe = self.params.get('timeframe', None)

        suffix = f'_{self.period}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.vol_ma_col = f'volume_ma{suffix}'
        self.vol_std_col = f'volume_std{suffix}'

    def calculate(self) -> 'WhaleIndicator':
        """ Core calculation logic remains the same. """
        df_for_calc = self.df
        if len(df_for_calc) < self.period:
            logger.warning(f"Not enough data for Whale Indicator on {self.timeframe or 'base'}.")
            self.df[self.vol_ma_col] = np.nan
            self.df[self.vol_std_col] = np.nan
            return self

        min_p = max(2, self.period // 2)
        self.df[self.vol_ma_col] = df_for_calc['volume'].rolling(window=self.period, min_periods=min_p).mean()
        self.df[self.vol_std_col] = df_for_calc['volume'].rolling(window=self.period, min_periods=min_p).std(ddof=0)

        return self

    def analyze(self) -> Dict[str, Any]:
        """ Provides a deep, statistical analysis including climactic volume detection. """
        required_cols = [self.vol_ma_col, self.vol_std_col, 'close', 'volume']
        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 1:
            return {"status": "Insufficient Data"}

        last_candle = valid_df.iloc[-1]
        
        last_volume = last_candle['volume']
        avg_volume = last_candle[self.vol_ma_col]
        std_volume = last_candle[self.vol_std_col]
        
        # Dual Threshold Calculation
        whale_threshold = avg_volume + (std_volume * self.stdev_multiplier)
        climactic_threshold = avg_volume + (std_volume * self.climactic_multiplier)
        
        is_whale_activity = last_volume > whale_threshold
        # ✅ NEW: Climactic volume is a higher-grade event
        is_climactic_volume = last_volume > climactic_threshold
        
        spike_score = (last_volume - avg_volume) / std_volume if std_volume > 0 else 0
        
        pressure = "Neutral"
        if is_whale_activity: # Pressure is determined by general whale activity
            if last_candle['close'] > last_candle['open']:
                pressure = "Buying Pressure"
            elif last_candle['close'] < last_candle['open']:
                pressure = "Selling Pressure"
            else:
                pressure = "Indecisive"

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
                "is_climactic_volume": is_climactic_volume, # The new, powerful data point
                "spike_score": round(spike_score, 2),
                "pressure": pressure,
                "summary": summary
            }
        }
