import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class WhaleIndicator(BaseIndicator):
    """
    Whale Activity Detector - Definitive, World-Class Version (v4.0 - Final Architecture)
    ------------------------------------------------------------------------------------
    This version transforms the indicator into a quantitative tool. It uses statistical
    methods (mean + standard deviation) to dynamically detect anomalous volume spikes.
    It adheres to the final AiSignalPro architecture.
    """
    dependencies: list = []

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.period = int(self.params.get('period', 20))
        self.stdev_multiplier = float(self.params.get('stdev_multiplier', 3.0))
        self.timeframe = self.params.get('timeframe', None)

        suffix = f'_{self.period}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.vol_ma_col = f'volume_ma{suffix}'
        self.vol_std_col = f'volume_std{suffix}'

    def _calculate_volume_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        """The core logic for calculating rolling volume metrics."""
        res = pd.DataFrame(index=df.index)
        min_p = max(2, self.period // 2)
        res[self.vol_ma_col] = df['volume'].rolling(window=self.period, min_periods=min_p).mean()
        res[self.vol_std_col] = df['volume'].rolling(window=self.period, min_periods=min_p).std(ddof=0)
        return res

    def calculate(self) -> 'WhaleIndicator':
        """
        ✨ FINAL ARCHITECTURE: No resampling. Just pure calculation.
        The dataframe received is already at the correct timeframe.
        """
        df_for_calc = self.df

        required_cols = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in df_for_calc.columns for col in required_cols):
            logger.error(f"DataFrame for {self.timeframe or 'base'} is missing one or more required OHLCV columns.")
            return self

        if len(df_for_calc) < self.period:
            logger.warning(f"Not enough data for Whale Indicator on {self.timeframe or 'base'}.")
            self.df[self.vol_ma_col] = np.nan
            self.df[self.vol_std_col] = np.nan
            return self

        volume_metrics = self._calculate_volume_metrics(df_for_calc)
        
        self.df[self.vol_ma_col] = volume_metrics[self.vol_ma_col]
        self.df[self.vol_std_col] = volume_metrics[self.vol_std_col]

        return self

    def analyze(self) -> Dict[str, Any]:
        """
        Provides a deep, statistical analysis of the last closed candle's volume.
        This powerful analysis logic remains unchanged.
        """
        required_cols = [self.vol_ma_col, self.vol_std_col, 'open', 'high', 'low', 'close', 'volume']
        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 1:
            return {"status": "Insufficient Data", "analysis": {}}

        last_candle = valid_df.iloc[-1]
        
        last_volume = last_candle['volume']
        avg_volume = last_candle[self.vol_ma_col]
        std_volume = last_candle[self.vol_std_col]
        
        dynamic_threshold = avg_volume + (std_volume * self.stdev_multiplier)
        
        status = "Normal Activity"; pressure = "Neutral"
        is_whale_activity = last_volume > dynamic_threshold
        
        spike_score = (last_volume - avg_volume) / std_volume if std_volume > 0 else 0
        
        if is_whale_activity:
            status = "Whale Activity Detected"
            mid_price = (last_candle['high'] + last_candle['low']) / 2
            if last_candle['close'] > mid_price:
                pressure = "Buying Pressure"
            elif last_candle['close'] < mid_price:
                pressure = "Selling Pressure"
            else:
                pressure = "Indecisive"

        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "values": {
                "last_volume": last_volume,
                "avg_volume": round(avg_volume, 2),
                "volume_stdev": round(std_volume, 2),
                "calculated_threshold": round(dynamic_threshold, 2),
            },
            "analysis": {
                "is_whale_activity": is_whale_activity,
                "spike_score": round(spike_score, 2),
                "pressure": pressure,
                "summary": status
            }
        }
