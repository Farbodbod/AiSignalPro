import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

# اطمینان حاصل کنید که این اندیکاتور از فایل مربوطه وارد شده‌ است
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class WhaleIndicator(BaseIndicator):
    """
    Whale Activity Detector - Definitive, Statistical, MTF & World-Class Version
    -----------------------------------------------------------------------------
    This version transforms the indicator into a quantitative tool. It uses
    statistical methods (mean + standard deviation) to dynamically detect
    anomalous volume spikes, and analyzes candlestick structure to infer the
    pressure behind the activity. It's fully integrated with the AiSignalPro
    MTF architecture.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        # --- Parameters ---
        self.params = kwargs.get('params', {})
        self.period = int(self.params.get('period', 20))
        # This multiplier is now for the standard deviation (Z-score)
        self.stdev_multiplier = float(self.params.get('stdev_multiplier', 3.0))
        self.timeframe = self.params.get('timeframe', None)

        # --- Dynamic Column Naming ---
        suffix = f'_{self.period}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.vol_ma_col = f'volume_ma{suffix}'
        self.vol_std_col = f'volume_std{suffix}'

    def _calculate_volume_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        """The core logic for calculating rolling volume metrics."""
        res = pd.DataFrame(index=df.index)
        # Using min_periods ensures we get values sooner, which can be useful.
        min_p = max(2, self.period // 2)
        res[self.vol_ma_col] = df['volume'].rolling(window=self.period, min_periods=min_p).mean()
        res[self.vol_std_col] = df['volume'].rolling(window=self.period, min_periods=min_p).std(ddof=0)
        return res

    def calculate(self) -> 'WhaleIndicator':
        """Orchestrates the MTF calculation for volume metrics."""
        base_df = self.df
        
        # ✨ MTF LOGIC: Resample data if a timeframe is specified
        if self.timeframe:
            if not isinstance(base_df.index, pd.DatetimeIndex):
                raise TypeError("DataFrame index must be a DatetimeIndex for MTF.")
            rules = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}
            calc_df = base_df.resample(self.timeframe, label='right', closed='right').apply(rules).dropna()
        else:
            calc_df = base_df.copy()

        required_cols = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in calc_df.columns for col in required_cols):
            logger.error("DataFrame is missing one or more required OHLCV columns.")
            return self

        volume_metrics = self._calculate_volume_metrics(calc_df)
        
        # --- Map results back to the original dataframe if MTF ---
        if self.timeframe:
            final_results = volume_metrics.reindex(base_df.index, method='ffill')
            for col in final_results.columns: self.df[col] = final_results[col]
        else:
            for col in volume_metrics.columns: self.df[col] = volume_metrics[col]

        return self

    def analyze(self) -> Dict[str, Any]:
        """Provides a deep, statistical analysis of the last closed candle's volume."""
        required_cols = [self.vol_ma_col, self.vol_std_col, 'open', 'high', 'low', 'close', 'volume']
        
        # ✨ Bias-Free: Drop all NaNs first
        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 1:
            return {"status": "Insufficient Data", "analysis": {}}

        # ✨ Bias-Free: Analyze the last fully closed candle's data
        last_candle = valid_df.iloc[-1]
        
        last_volume = last_candle['volume']
        avg_volume = last_candle[self.vol_ma_col]
        std_volume = last_candle[self.vol_std_col]
        
        # --- ✨ Dynamic Threshold Calculation ---
        dynamic_threshold = avg_volume + (std_volume * self.stdev_multiplier)
        
        status = "Normal Activity"
        pressure = "Neutral"
        is_whale_activity = last_volume > dynamic_threshold
        
        # Calculate spike score (how many standard deviations above the mean)
        spike_score = (last_volume - avg_volume) / std_volume if std_volume > 0 else 0
        
        if is_whale_activity:
            status = "Whale Activity Detected"
            # --- ✨ Nuanced Pressure Analysis ---
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
                "spike_score": round(spike_score, 2), # A powerful metric for filtering
                "pressure": pressure,
                "summary": status
            }
        }
