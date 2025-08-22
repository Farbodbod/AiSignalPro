# backend/engines/indicators/ema_cross.py (v6.1 - The Smoothed Flow Edition)
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Optional

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class EMACrossIndicator(BaseIndicator):
    """
    EMA Cross - (v6.1 - The Smoothed Flow Edition)
    -------------------------------------------------------------------------
    This world-class version introduces a "Smart Flow" analysis. Instead of
    relying on a noisy single-period difference, it now calculates a smoothed
    slope of the EMAs, providing a much more robust and reliable trend
    alignment confirmation. All previous hardening and features are preserved.
    """
    dependencies: list = []

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.short_period = int(self.params.get('short_period', 9))
        self.long_period = int(self.params.get('long_period', 21))
        self.timeframe = self.params.get('timeframe', None)
        self.use_volume_filter = bool(self.params.get('use_volume_filter', True))
        self.rvol_period = int(self.params.get('rvol_period', 20))
        self.rvol_threshold = float(self.params.get('rvol_threshold', 1.5))

        if self.short_period >= self.long_period:
            raise ValueError(f"Short period ({self.short_period}) must be less than long period ({self.long_period}).")

        suffix = f'_{self.short_period}_{self.long_period}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        else: suffix += '_base'

        self.short_ema_col = f'ema{suffix}_short'
        self.long_ema_col = f'ema{suffix}_long'
        self.signal_col = f'ema_cross_signal{suffix}'
        self.rvol_col = f'rvol{suffix}_{self.rvol_period}'
        self.short_ema_slope_col = f'{self.short_ema_col}_slope'
        self.long_ema_slope_col = f'{self.long_ema_col}_slope'


    def calculate(self) -> 'EMACrossIndicator':
        if len(self.df) < self.long_period:
            logger.warning(f"Not enough data for EMA Cross on {self.timeframe or 'base'}.")
            return self

        close = pd.to_numeric(self.df['close'], errors='coerce')
        
        short_ema = close.ewm(span=self.short_period, adjust=False).mean()
        long_ema = close.ewm(span=self.long_period, adjust=False).mean()
        self.df[self.short_ema_col] = short_ema
        self.df[self.long_ema_col] = long_ema

        # ✅ SMART FLOW ANALYSIS (v6.1): Calculate a smoothed slope for robust trend alignment.
        smoothing_period = 3 # A small EMA to smooth out the slope calculation
        self.df[self.short_ema_slope_col] = short_ema.diff().ewm(span=smoothing_period, adjust=False).mean()
        self.df[self.long_ema_slope_col] = long_ema.diff().ewm(span=smoothing_period, adjust=False).mean()

        prev_short = short_ema.shift(1); prev_long = long_ema.shift(1)
        bullish_cross = (prev_short <= prev_long) & (short_ema > long_ema)
        bearish_cross = (prev_short >= prev_long) & (short_ema < long_ema)
        self.df[self.signal_col] = np.where(bullish_cross, 1, np.where(bearish_cross, -1, 0))

        if self.use_volume_filter:
            if 'volume' in self.df.columns:
                vol_ma = self.df['volume'].rolling(window=self.rvol_period).mean().replace(0, np.nan)
                rvol = self.df['volume'] / vol_ma
                rvol.replace([np.inf, -np.inf], np.nan, inplace=True)
                # The robust ffill->bfill logic is preserved for maximum stability.
                self.df[self.rvol_col] = rvol.ffill(limit=3).bfill(limit=2)
            else:
                self.df[self.rvol_col] = np.nan
        return self

    def analyze(self) -> Dict[str, Any]:
        required_cols = [self.short_ema_col, self.long_ema_col, self.signal_col, self.short_ema_slope_col, self.long_ema_slope_col]
        empty_analysis = {"values": {}, "analysis": {}}
        if not all(col in self.df.columns for col in required_cols):
            return {"status": "Calculation Incomplete", **empty_analysis}
            
        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 1: return {"status": "Insufficient Data", **empty_analysis}

        last = valid_df.iloc[-1]
        
        signal_val = int(last[self.signal_col])
        primary_event = "Neutral"
        if signal_val == 1: primary_event = "Bullish Crossover"
        elif signal_val == -1: primary_event = "Bearish Crossover"
        
        short_ema, long_ema = last[self.short_ema_col], last[self.long_ema_col]
        # Use the new, smoothed slope for analysis
        short_slope, long_slope = last[self.short_ema_slope_col], last[self.long_ema_slope_col]
        
        trend_is_aligned = (short_slope > 0 and long_slope > 0) if "Bullish" in primary_event \
                      else (short_slope < 0 and long_slope < 0) if "Bearish" in primary_event \
                      else False
        
        volume_confirmed = False
        last_rvol = last.get(self.rvol_col)
        if self.use_volume_filter and pd.notna(last_rvol):
            if last_rvol > self.rvol_threshold:
                volume_confirmed = True

        final_signal, strength = "Hold", "Neutral"
        if primary_event != "Neutral":
            if trend_is_aligned and volume_confirmed:
                strength, final_signal = "Strong", "Buy" if "Bullish" in primary_event else "Sell"
            elif trend_is_aligned or volume_confirmed:
                strength, final_signal = "Medium", "Buy" if "Bullish" in primary_event else "Sell"
            else:
                strength = "Weak"

        values_content = { "short_ema": round(short_ema, 5), "long_ema": round(long_ema, 5), "rvol": round(last_rvol, 2) if pd.notna(last_rvol) else 0.0 }
        analysis_content = {
            "signal": final_signal, "strength": strength,
            "primary_event": primary_event,
            "confirmation": { "trend_is_aligned": trend_is_aligned, "volume_confirmed": volume_confirmed }
        }

        return {
            "status": "OK", "timeframe": self.timeframe or 'Base',
            "values": values_content,
            "analysis": analysis_content
        }
