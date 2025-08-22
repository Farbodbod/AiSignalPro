# backend/engines/indicators/donchian_channel.py (v4.0 - The Multi-Frame Engine)
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Optional

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class DonchianChannelIndicator(BaseIndicator):
    """
    Donchian Channel - (v4.0 - The Multi-Frame Engine)
    ----------------------------------------------------------------------------------
    This world-class version is a complete market structure engine. It introduces
    Multi-Timeframe Intelligence, a rich analysis layer (Width, Position, Bias),
    and configurable breakout modes. The architecture is now fully standardized,
    using robust dependency injection and a Sentinel-compliant output.
    """
    dependencies = ['atr'] # Optional dependency for ATR filter

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.period = int(self.params.get('period', 20))
        self.timeframe = self.params.get('timeframe', None) # Chart timeframe
        self.source_timeframe = self.params.get('source_timeframe', self.timeframe) # Timeframe for calculation
        
        # ✅ DYNAMIC ARCHITECTURE: Column names are now fully explicit and conflict-proof.
        suffix = f'_{self.period}'
        if self.source_timeframe: suffix += f'_{self.source_timeframe}'
        else: suffix += '_base'
        
        self.upper_col = f'donchian_upper{suffix}'
        self.lower_col = f'donchian_lower{suffix}'
        self.middle_col = f'donchian_middle{suffix}'

    def calculate(self) -> 'DonchianChannelIndicator':
        # ✅ MULTI-FRAME INTELLIGENCE: Use source_timeframe for calculation if provided.
        if self.source_timeframe and self.source_timeframe != self.timeframe:
            try:
                ohlc_agg = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}
                df_for_calc = self.df.resample(self.source_timeframe).agg(ohlc_agg).dropna()
            except Exception as e:
                logger.error(f"Failed to resample for Donchian from {self.timeframe} to {self.source_timeframe}: {e}")
                return self
        else:
            df_for_calc = self.df

        if len(df_for_calc) < self.period:
            logger.warning(f"Not enough data for Donchian on source timeframe {self.source_timeframe}.")
            return self

        upper_band = df_for_calc['high'].rolling(window=self.period).max()
        lower_band = df_for_calc['low'].rolling(window=self.period).min()
        
        # Backfill to align with current timeframe and then ffill
        self.df[self.upper_col] = upper_band.reindex(self.df.index, method='bfill').ffill()
        self.df[self.lower_col] = lower_band.reindex(self.df.index, method='bfill').ffill()
        self.df[self.middle_col] = (self.df[self.upper_col] + self.df[self.lower_col]) / 2
        return self

    def analyze(self) -> Dict[str, Any]:
        required_cols = [self.upper_col, self.lower_col, self.middle_col, 'close', 'high', 'low']
        empty_analysis = {"values": {}, "analysis": {}}
        if not all(col in self.df.columns for col in required_cols):
            return {"status": "Calculation Incomplete", **empty_analysis}

        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 2: return {"status": "Insufficient Data", **empty_analysis}

        last = valid_df.iloc[-1]; prev = valid_df.iloc[-2]
        
        # ✅ ENHANCED ANALYSIS: Calculate rich context metrics
        channel_width = ((last[self.upper_col] - last[self.lower_col]) / last[self.middle_col]) * 100 if last[self.middle_col] > 0 else 0
        channel_range = (last[self.upper_col] - last[self.lower_col])
        position_in_channel = ((last['close'] - last[self.lower_col]) / channel_range) * 100 if channel_range > 0 else 50
        bias = "Bullish" if last['close'] > last[self.middle_col] else "Bearish"

        # ✅ DYNAMIC BREAKOUT MODES
        breakout_mode = self.params.get("breakout_mode", "close")
        signal = "Neutral"
        if breakout_mode == "close":
            if last['close'] > prev[self.upper_col]: signal = "Buy"
            elif last['close'] < prev[self.lower_col]: signal = "Sell"
        elif breakout_mode == "intrabar":
            if last['high'] > last[self.upper_col]: signal = "Buy"
            elif last['low'] < last[self.lower_col]: signal = "Sell"

        values_content = {
            "upper_band": round(last[self.upper_col], 5),
            "middle_band": round(last[self.middle_col], 5),
            "lower_band": round(last[self.lower_col], 5),
        }
        analysis_content = {
            "signal": signal,
            "bias": bias,
            "channel_width_percent": round(channel_width, 2),
            "position_in_channel_percent": round(position_in_channel, 2)
        }
        
        return {
            "status": "OK", "timeframe": self.timeframe or 'Base',
            "values": values_content, "analysis": analysis_content
        }
