# backend/engines/indicators/volume.py (v1.0 - Hardened Analysis Edition)

import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class VolumeIndicator(BaseIndicator):
    """
    Volume Indicator - (v1.0 - Hardened Analysis Edition)
    ---------------------------------------------------------------------------
    This is a world-class, feature-rich volume indicator designed for the
    AiSignalPro architecture. It goes beyond simple volume moving averages to
    provide deep, actionable insights.

    Key Features:
    - Calculates both short-term and long-term volume moving averages.
    - Determines the volume "trend" (increasing or decreasing participation).
    - Identifies climactic volume spikes using standard deviation.
    - Hardened against NaN propagation using limited forward-fills.
    - Provides a rich, standardized analysis output for strategy consumption.
    """
    # This indicator has no external dependencies; it uses the base 'volume' column.
    dependencies: list = []

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.period = int(self.params.get('period', 20))
        self.long_period = int(self.params.get('long_period', 50))
        self.climactic_std_threshold = float(self.params.get('climactic_std_threshold', 2.5))
        self.timeframe = self.params.get('timeframe', None)
        
        suffix = f'_{self.period}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        
        self.volume_ma_col = f'volume_ma{suffix}'
        self.volume_ma_long_col = f'volume_ma_long_{self.long_period}{suffix}'
        self.volume_std_col = f'volume_std{suffix}'

    def calculate(self) -> 'VolumeIndicator':
        """Calculates Volume MA, Long Volume MA, and Volume STD."""
        df_for_calc = self.df
        
        if 'volume' not in df_for_calc.columns or len(df_for_calc) < self.long_period:
            logger.warning(f"Not enough data or missing 'volume' column for VolumeIndicator on timeframe {self.timeframe or 'base'}.")
            for col in [self.volume_ma_col, self.volume_ma_long_col, self.volume_std_col]:
                self.df[col] = np.nan
            return self

        # Calculate short-term and long-term moving averages of volume
        volume_ma = df_for_calc['volume'].rolling(window=self.period).mean()
        volume_ma_long = df_for_calc['volume'].rolling(window=self.long_period).mean()
        
        # Calculate the standard deviation of volume for spike detection
        volume_std = df_for_calc['volume'].rolling(window=self.period).std()
        
        # Hardened Fill: Use a limited forward-fill to prevent stale data propagation
        fill_limit = 3 
        self.df[self.volume_ma_col] = volume_ma.ffill(limit=fill_limit)
        self.df[self.volume_ma_long_col] = volume_ma_long.ffill(limit=fill_limit)
        self.df[self.volume_std_col] = volume_std.ffill(limit=fill_limit)
            
        return self

    def analyze(self) -> Dict[str, Any]:
        """Analyzes the latest volume data to provide actionable insights."""
        required_cols = [self.volume_ma_col, self.volume_ma_long_col, self.volume_std_col]
        empty_analysis = {"values": {}, "analysis": {}}

        if any(col not in self.df.columns for col in required_cols):
            return {"status": "Calculation Incomplete - Columns missing", **empty_analysis}

        valid_df = self.df.dropna(subset=required_cols)
        if valid_df.empty:
            return {"status": "Insufficient Data", **empty_analysis}
        
        last = valid_df.iloc[-1]
        
        latest_volume = last['volume']
        latest_volume_ma = last[self.volume_ma_col]
        latest_volume_ma_long = last[self.volume_ma_long_col]
        latest_volume_std = last[self.volume_std_col]

        # --- Analysis Logic ---
        is_below_average = latest_volume < latest_volume_ma
        is_above_average = not is_below_average

        # Determine volume trend by comparing short-term and long-term MAs
        if latest_volume_ma > latest_volume_ma_long:
            volume_trend = "Increasing"
        elif latest_volume_ma < latest_volume_ma_long:
            volume_trend = "Decreasing"
        else:
            volume_trend = "Neutral"

        # Check for climactic volume spikes
        is_climactic = is_above_average and (latest_volume > (latest_volume_ma + self.climactic_std_threshold * latest_volume_std))

        summary = "Low Volume" if is_below_average else "High Volume"
        if is_climactic:
            summary = "Climactic Volume Spike"

        values_content = {
            "volume": float(latest_volume),
            "volume_ma": float(latest_volume_ma),
            "volume_ma_long": float(latest_volume_ma_long),
            "volume_std": float(latest_volume_std),
        }

        analysis_content = {
            "is_below_average": bool(is_below_average),
            "is_above_average": bool(is_above_average),
            "is_climactic_volume": bool(is_climactic),
            "volume_trend": volume_trend,
            "summary": summary
        }

        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "values": values_content,
            "analysis": analysis_content
        }
