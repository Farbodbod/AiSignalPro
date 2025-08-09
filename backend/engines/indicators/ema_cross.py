import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

# اطمینان حاصل کنید که این اندیکاتور از فایل مربوطه وارد شده‌ است
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class EMACrossIndicator(BaseIndicator):
    """
    EMA Cross - Definitive, Strategy-Ready, MTF & World-Class Version
    --------------------------------------------------------------------
    This version is a mini-strategy engine. It doesn't just find crossovers;
    it validates them against volume and analyzes their strength, providing
    rich, context-aware signals perfect for a fully automated trading system.
    It adheres to the standard AiSignalPro MTF architecture.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        # --- Parameters ---
        self.params = kwargs.get('params', {})
        self.short_period = int(self.params.get('short_period', 9))
        self.long_period = int(self.params.get('long_period', 21))
        self.timeframe = self.params.get('timeframe', None)
        # --- Volume Confirmation Parameters ---
        self.use_volume_filter = bool(self.params.get('use_volume_filter', True))
        self.rvol_period = int(self.params.get('rvol_period', 20))
        self.rvol_threshold = float(self.params.get('rvol_threshold', 1.5))

        if self.short_period >= self.long_period:
            raise ValueError(f"Short period ({self.short_period}) must be less than long period ({self.long_period}).")

        # --- Dynamic Column Naming ---
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
        
        # EMAs and Crossover Signal
        res[self.short_ema_col] = close.ewm(span=self.short_period, adjust=False).mean()
        res[self.long_ema_col] = close.ewm(span=self.long_period, adjust=False).mean()
        prev_short = res[self.short_ema_col].shift(1)
        prev_long = res[self.long_ema_col].shift(1)
        bullish_cross = (prev_short <= prev_long) & (res[self.short_ema_col] > res[self.long_ema_col])
        bearish_cross = (prev_short >= prev_long) & (res[self.short_ema_col] < res[self.long_ema_col])
        res[self.signal_col] = np.where(bullish_cross, 1, np.where(bearish_cross, -1, 0))

        # Relative Volume for Confirmation
        if self.use_volume_filter:
            vol_ma = df['volume'].rolling(window=self.rvol_period).mean().replace(0, np.nan)
            res[self.rvol_col] = df['volume'] / vol_ma
            
        return res

    def calculate(self) -> 'EMACrossIndicator':
        """Orchestrates the MTF calculation."""
        base_df = self.df
        
        if self.timeframe:
            if not isinstance(base_df.index, pd.DatetimeIndex): raise TypeError("DatetimeIndex required for MTF.")
            rules = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}
            calc_df = base_df.resample(self.timeframe, label='right', closed='right').apply(rules).dropna()
        else:
            calc_df = base_df.copy()

        if len(calc_df) < self.long_period: logger.warning(f"Not enough data for EMA Cross on {self.timeframe or 'base'}."); return self

        results = self._calculate_metrics(calc_df)
        
        if self.timeframe:
            final_results = results.reindex(base_df.index, method='ffill')
            for col in final_results.columns: self.df[col] = final_results[col]
        else:
            for col in results.columns: self.df[col] = results[col]

        return self

    def analyze(self) -> Dict[str, Any]:
        """Provides a deep, context-rich analysis suitable for automated systems."""
        required_cols = [self.short_ema_col, self.long_ema_col, self.signal_col]
        
        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 2: return {"status": "Insufficient Data"}

        last = valid_df.iloc[-1]; prev = valid_df.iloc[-2]
        
        signal_val = int(last[self.signal_col])
        primary_signal = "Neutral"
        if signal_val == 1: primary_signal = "Bullish Crossover"
        elif signal_val == -1: primary_signal = "Bearish Crossover"
        
        # --- Contextual Analysis for Automation ---
        short_ema, long_ema = last[self.short_ema_col], last[self.long_ema_col]
        
        # 1. Trend Alignment (Slope of both EMAs)
        short_slope = short_ema - prev[self.short_ema_col]
        long_slope = long_ema - prev[self.long_ema_col]
        trend_is_aligned = (short_slope > 0 and long_slope > 0) if "Bullish" in primary_signal \
                      else (short_slope < 0 and long_slope < 0) if "Bearish" in primary_signal \
                      else False
        
        # 2. Volume Confirmation
        volume_confirmed = False
        if self.use_volume_filter and self.rvol_col in last and pd.notna(last[self.rvol_col]):
            if last[self.rvol_col] > self.rvol_threshold:
                volume_confirmed = True

        # 3. Final Signal with Strength
        final_signal = "Hold"
        strength = "N/A"
        if primary_signal != "Neutral":
            if trend_is_aligned and volume_confirmed:
                strength = "Strong"
                final_signal = "Buy" if "Bullish" in primary_signal else "Sell"
            elif trend_is_aligned or volume_confirmed:
                strength = "Medium"
                final_signal = "Buy" if "Bullish" in primary_signal else "Sell"
            else:
                strength = "Weak"
                final_signal = "Hold" # We can choose to ignore weak signals

        return {
            "status": "OK", "timeframe": self.timeframe or 'Base',
            "values": { "short_ema": round(short_ema, 5), "long_ema": round(long_ema, 5), "rvol": round(last.get(self.rvol_col, 0), 2)},
            "analysis": {
                "signal": final_signal,
                "strength": strength,
                "primary_event": primary_signal,
                "confirmation": { "trend_is_aligned": trend_is_aligned, "volume_confirmed": volume_confirmed }
            }
        }
