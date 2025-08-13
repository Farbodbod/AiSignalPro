import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Optional

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class EMACrossIndicator(BaseIndicator):
    """
    EMA Cross - (v5.0 - Harmonized API)
    -------------------------------------------------------------------------
    This version is now a first-class citizen of the universal engine. It includes
    standardized `get_col_name` static methods, making it fully compatible
    with strategy-specific configurations and future-proofing its architecture.
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

        # ✅ HARMONIZED: Column names are now generated using the official static methods
        self.short_ema_col, self.long_ema_col, self.signal_col, self.rvol_col = EMACrossIndicator.get_col_names(self.params, self.timeframe)

    @staticmethod
    def get_col_names(params: Dict[str, Any], timeframe: Optional[str] = None) -> tuple:
        """ ✅ NEW: The official, standardized method for generating all column names. """
        short_period = params.get('short_period', 9)
        long_period = params.get('long_period', 21)
        rvol_period = params.get('rvol_period', 20)

        suffix = f'_{short_period}_{long_period}'
        if timeframe: suffix += f'_{timeframe}'
        
        short_ema_col = f'ema{suffix}_short'
        long_ema_col = f'ema{suffix}_long'
        signal_col = f'ema_cross_signal{suffix}'
        rvol_col = f'rvol{suffix}_{rvol_period}'
        return short_ema_col, long_ema_col, signal_col, rvol_col

    def calculate(self) -> 'EMACrossIndicator':
        """ Core calculation logic is unchanged and robust. """
        df_for_calc = self.df
        
        if len(df_for_calc) < self.long_period:
            logger.warning(f"Not enough data for EMA Cross on {self.timeframe or 'base'}.")
            return self

        close = pd.to_numeric(df_for_calc['close'], errors='coerce')
        
        short_ema = close.ewm(span=self.short_period, adjust=False).mean()
        long_ema = close.ewm(span=self.long_period, adjust=False).mean()
        self.df[self.short_ema_col] = short_ema
        self.df[self.long_ema_col] = long_ema

        prev_short = short_ema.shift(1)
        prev_long = long_ema.shift(1)
        bullish_cross = (prev_short <= prev_long) & (short_ema > long_ema)
        bearish_cross = (prev_short >= prev_long) & (short_ema < long_ema)
        self.df[self.signal_col] = np.where(bullish_cross, 1, np.where(bearish_cross, -1, 0))

        if self.use_volume_filter:
            if 'volume' in df_for_calc.columns:
                vol_ma = df_for_calc['volume'].rolling(window=self.rvol_period).mean().replace(0, np.nan)
                self.df[self.rvol_col] = df_for_calc['volume'] / vol_ma
            else:
                self.df[self.rvol_col] = np.nan
        return self

    def analyze(self) -> Dict[str, Any]:
        """ Analysis logic is unchanged, deep, and robust. """
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
                "signal": final_signal, "strength": strength,
                "primary_event": primary_event,
                "confirmation": { "trend_is_aligned": trend_is_aligned, "volume_confirmed": volume_confirmed }
            }
        }
