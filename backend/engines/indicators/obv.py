import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class ObvIndicator(BaseIndicator):
    """
    On-Balance Volume (OBV) - Definitive, World-Class Version (v4.0 - Final Architecture)
    ------------------------------------------------------------------------------------
    This version elevates OBV into a sophisticated trend strength analysis engine.
    It adheres to the final AiSignalPro architecture by calculating on the
    pre-resampled dataframe.
    """
    dependencies: list = []

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.signal_period = int(self.params.get('signal_period', 20))
        self.rvol_period = int(self.params.get('rvol_period', 20))
        self.price_ma_period = int(self.params.get('price_ma_period', 20))
        self.rvol_threshold = float(self.params.get('rvol_threshold', 1.5))
        self.timeframe = self.params.get('timeframe', None)

        suffix = f'_{self.timeframe}' if self.timeframe else ''
        self.obv_col = f'obv{suffix}'
        self.obv_signal_col = f'obv_signal_{self.signal_period}{suffix}'
        self.rvol_col = f'rvol_{self.rvol_period}{suffix}'
        self.price_ma_col = f'price_ma_{self.price_ma_period}{suffix}'

    def _calculate_obv_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        """The core logic for calculating OBV and its related confirmation metrics."""
        res = pd.DataFrame(index=df.index)
        
        obv_raw = np.where(df['close'] > df['close'].shift(1), df['volume'],
                  np.where(df['close'] < df['close'].shift(1), -df['volume'], 0)).cumsum()
        
        # ✨ BUGFIX: Convert NumPy array to pandas Series before calling .ewm()
        obv_series = pd.Series(obv_raw, index=df.index)
        res[self.obv_col] = obv_series
        res[self.obv_signal_col] = obv_series.ewm(span=self.signal_period, adjust=False).mean()
        
        vol_ma = df['volume'].rolling(window=self.rvol_period).mean().replace(0, np.nan)
        res[self.rvol_col] = df['volume'] / vol_ma
        
        res[self.price_ma_col] = df['close'].ewm(span=self.price_ma_period, adjust=False).mean()
        
        return res

    def calculate(self) -> 'ObvIndicator':
        """
        ✨ FINAL ARCHITECTURE: No resampling. Just pure calculation.
        The dataframe received is already at the correct timeframe.
        """
        df_for_calc = self.df

        if len(df_for_calc) < max(self.signal_period, self.rvol_period, self.price_ma_period):
            logger.warning(f"Not enough data for OBV on timeframe {self.timeframe or 'base'}.")
            return self

        obv_results = self._calculate_obv_metrics(df_for_calc)
        
        for col in obv_results.columns:
            self.df[col] = obv_results[col]

        return self

    def analyze(self) -> Dict[str, Any]:
        """
        Provides a deep, confirmation-based analysis of volume-price dynamics.
        This powerful analysis logic remains unchanged.
        """
        required_cols = [self.obv_col, self.obv_signal_col, self.rvol_col, self.price_ma_col, 'close']
        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 2:
            return {"status": "Insufficient Data", "analysis": {}}

        last = valid_df.iloc[-1]
        prev = valid_df.iloc[-2]

        primary_signal = "Neutral"
        if prev[self.obv_col] <= prev[self.obv_signal_col] and last[self.obv_col] > last[self.obv_signal_col]:
            primary_signal = "Bullish Crossover"
        elif prev[self.obv_col] >= prev[self.obv_signal_col] and last[self.obv_col] < last[self.obv_signal_col]:
            primary_signal = "Bearish Crossover"
            
        volume_confirmed = last[self.rvol_col] > self.rvol_threshold
        price_confirmed = False
        if "Bullish" in primary_signal:
            price_confirmed = last['close'] > last[self.price_ma_col]
        elif "Bearish" in primary_signal:
            price_confirmed = last['close'] < last[self.price_ma_col]
            
        final_signal = "Hold"
        if primary_signal != "Neutral":
            if volume_confirmed and price_confirmed:
                final_signal = f"Strong {primary_signal.split(' ')[0]}"
            elif volume_confirmed or price_confirmed:
                final_signal = f"Weak {primary_signal.split(' ')[0]}"
            else:
                final_signal = "Unconfirmed Crossover"
        
        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "values": {
                "obv": int(last[self.obv_col]),
                "obv_signal_line": int(last[self.obv_signal_col]),
                "rvol": round(last[self.rvol_col], 2),
                "price_ma": round(last[self.price_ma_col], 5)
            },
            "analysis": {
                "signal": final_signal,
                "primary_event": primary_signal,
                "confirmation": {
                    "volume_confirmed": volume_confirmed,
                    "price_confirmed": price_confirmed
                }
            }
        }
