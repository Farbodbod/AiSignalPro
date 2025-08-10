import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class EMACrossIndicator(BaseIndicator):
    """
    EMA Cross - Definitive, World-Class Version (v4.0 - Final Architecture)
    -------------------------------------------------------------------------
    This version is a mini-strategy engine. It validates crossovers against
    volume and trend alignment. It adheres to the final AiSignalPro architecture
    by performing its calculations on the pre-resampled dataframe.
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
        self.short_ema_col = f'ema{suffix}_short'
        self.long_ema_col = f'ema{suffix}_long'
        self.signal_col = f'ema_cross_signal{suffix}'
        self.rvol_col = f'rvol{suffix}_{self.rvol_period}'

    def _calculate_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        """The core logic for calculating EMAs, crossovers, and confirmation metrics."""
        res = pd.DataFrame(index=df.index)
        close = pd.to_numeric(df['close'], errors='coerce')
        
        res[self.short_ema_col] = close.ewm(span=self.short_period, adjust=False).mean()
        res[self.long_ema_col] = close.ewm(span=self.long_period, adjust=False).mean()
        prev_short = res[self.short_ema_col].shift(1)
        prev_long = res[self.long_ema_col].shift(1)
        bullish_cross = (prev_short <= prev_long) & (res[self.short_ema_col] > res[self.long_ema_col])
        bearish_cross = (prev_short >= prev_long) & (res[self.short_ema_col] < res[self.long_ema_col])
        res[self.signal_col] = np.where(bullish_cross, 1, np.where(bearish_cross, -1, 0))

        if self.use_volume_filter:
            if 'volume' in df.columns:
                vol_ma = df['volume'].rolling(window=self.rvol_period).mean().replace(0, np.nan)
                res[self.rvol_col] = df['volume'] / vol_ma
            else:
                res[self.rvol_col] = np.nan
                logger.warning(f"Volume column not found for RVOL calculation on timeframe {self.timeframe or 'base'}.")
            
        return res

    def calculate(self) -> 'EMACrossIndicator':
        """
        ✨ FINAL ARCHITECTURE: No resampling. Just pure calculation.
        The dataframe received is already at the correct timeframe.
        """
        df_for_calc = self.df
        
        if len(df_for_calc) < self.long_period:
            logger.warning(f"Not enough data for EMA Cross on {self.timeframe or 'base'}.")
            return self

        results = self._calculate_metrics(df_for_calc)
        
        for col in results.columns:
            self.df[col] = results[col]

        return self

    def analyze(self) -> Dict[str, Any]:
        """
        Provides a deep, context-rich analysis suitable for automated systems.
        This powerful analysis logic remains unchanged.
        """
        required_cols = [self.short_ema_col, self.long_ema_col, self.signal_col]
        
        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 2: return {"status": "Insufficient Data"}

        last = valid_df.iloc[-1]; prev = valid_df.iloc[-2]
        
        signal_val = int(last[self.signal_col])
        primary_event = "Neutral"
        if signal_val == 1: primary_event = "Bullish Crossover"
        elif signal_val == -1: primary_event = "Bearish Crossover"
        
        short_ema, long_ema = last[self.short_ema_col], last[self.long_ema_col]
        
        short_slope = short_ema - prev[self.short_ema_col]
        long_slope = long_ema - prev[self.long_ema_col]
        trend_is_aligned = (short_slope > 0 and long_slope > 0) if "Bullish" in primary_event \
                      else (short_slope < 0 and long_slope < 0) if "Bearish" in primary_event \
                      else False
        
        volume_confirmed = False
        if self.use_volume_filter and self.rvol_col in last and pd.notna(last[self.rvol_col]):
            if last[self.rvol_col] > self.rvol_threshold:
                volume_confirmed = True

        final_signal = "Hold"; strength = "N/A"
        if primary_event != "Neutral":
            if trend_is_aligned and volume_confirmed:
                strength = "Strong"; final_signal = "Buy" if "Bullish" in primary_event else "Sell"
            elif trend_is_aligned or volume_confirmed:
                strength = "Medium"; final_signal = "Buy" if "Bullish" in primary_event else "Sell"
            else:
                strength = "Weak"; final_signal = "Hold"

        return {
            "status": "OK", "timeframe": self.timeframe or 'Base',
            "values": { "short_ema": round(short_ema, 5), "long_ema": round(long_ema, 5), "rvol": round(last.get(self.rvol_col, 0), 2)},
            "analysis": {
                "signal": final_signal,
                "strength": strength,
                "primary_event": primary_event,
                "confirmation": { "trend_is_aligned": trend_is_aligned, "volume_confirmed": volume_confirmed }
            }
        }
