import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

# اطمینان حاصل کنید که این اندیکاتور از فایل مربوطه وارد شده‌ است
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class ObvIndicator(BaseIndicator):
    """
    On-Balance Volume (OBV) - Definitive, MTF, and Signal Confirmation World-Class Version
    ---------------------------------------------------------------------------------------
    This version elevates OBV into a sophisticated trend strength analysis engine. It features:
    - A smoothed signal line to reduce noise and generate reliable crossover signals.
    - A built-in confirmation engine that validates signals against Relative Volume (RVOL)
      and Price Action.
    - Full integration with the AiSignalPro MTF architecture.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        # --- Parameters ---
        self.params = kwargs.get('params', {})
        self.signal_period = int(self.params.get('signal_period', 20)) # For the OBV signal line
        self.rvol_period = int(self.params.get('rvol_period', 20))     # For Relative Volume
        self.price_ma_period = int(self.params.get('price_ma_period', 20)) # For Price Confirmation
        self.rvol_threshold = float(self.params.get('rvol_threshold', 1.5)) # RVOL must be > this for confirmation
        self.timeframe = self.params.get('timeframe', None)

        # --- Dynamic Column Naming ---
        suffix = f'_{self.timeframe}' if self.timeframe else ''
        self.obv_col = f'obv{suffix}'
        self.obv_signal_col = f'obv_signal_{self.signal_period}{suffix}'
        self.rvol_col = f'rvol_{self.rvol_period}{suffix}'
        self.price_ma_col = f'price_ma_{self.price_ma_period}{suffix}'

    def _calculate_obv_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        """The core logic for calculating OBV and its related confirmation metrics."""
        res = pd.DataFrame(index=df.index)
        
        # 1. Raw OBV
        obv = np.where(df['close'] > df['close'].shift(1), df['volume'],
              np.where(df['close'] < df['close'].shift(1), -df['volume'], 0)).cumsum()
        res[self.obv_col] = obv
        
        # 2. OBV Signal Line (for noise reduction)
        res[self.obv_signal_col] = obv.ewm(span=self.signal_period, adjust=False).mean()
        
        # 3. Relative Volume (RVOL) for confirmation
        vol_ma = df['volume'].rolling(window=self.rvol_period).mean().replace(0, np.nan)
        res[self.rvol_col] = df['volume'] / vol_ma
        
        # 4. Price MA for confirmation
        res[self.price_ma_col] = df['close'].ewm(span=self.price_ma_period, adjust=False).mean()
        
        return res

    def calculate(self) -> 'ObvIndicator':
        """Orchestrates the MTF calculation for OBV and its metrics."""
        base_df = self.df
        
        # ✨ MTF LOGIC: Resample data if a timeframe is specified
        if self.timeframe:
            if not isinstance(base_df.index, pd.DatetimeIndex):
                raise TypeError("DataFrame index must be a DatetimeIndex for MTF.")
            rules = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}
            calc_df = base_df.resample(self.timeframe, label='right', closed='right').apply(rules).dropna()
        else:
            calc_df = base_df.copy()

        if len(calc_df) < max(self.signal_period, self.rvol_period, self.price_ma_period):
            logger.warning(f"Not enough data for OBV on timeframe {self.timeframe or 'base'}.")
            return self

        obv_results = self._calculate_obv_metrics(calc_df)
        
        # --- Map results back to the original dataframe if MTF ---
        if self.timeframe:
            final_results = obv_results.reindex(base_df.index, method='ffill')
            for col in final_results.columns: self.df[col] = final_results[col]
        else:
            for col in obv_results.columns: self.df[col] = obv_results[col]

        return self

    def analyze(self) -> Dict[str, Any]:
        """Provides a deep, confirmation-based analysis of volume-price dynamics."""
        required_cols = [self.obv_col, self.obv_signal_col, self.rvol_col, self.price_ma_col, 'close']
        
        # ✨ Bias-Free Analysis
        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 2:
            return {"status": "Insufficient Data", "analysis": {}}

        last = valid_df.iloc[-1]
        prev = valid_df.iloc[-2]

        # --- 1. Primary Crossover Signal ---
        primary_signal = "Neutral"
        if prev[self.obv_col] <= prev[self.obv_signal_col] and last[self.obv_col] > last[self.obv_signal_col]:
            primary_signal = "Bullish Crossover"
        elif prev[self.obv_col] >= prev[self.obv_signal_col] and last[self.obv_col] < last[self.obv_signal_col]:
            primary_signal = "Bearish Crossover"
            
        # --- 2. Confirmation Filters ---
        volume_confirmed = last[self.rvol_col] > self.rvol_threshold
        price_confirmed = False
        if primary_signal == "Bullish Crossover":
            price_confirmed = last['close'] > last[self.price_ma_col]
        elif primary_signal == "Bearish Crossover":
            price_confirmed = last['close'] < last[self.price_ma_col]
            
        # --- 3. Final Aggregated Signal ---
        final_signal = "Hold"
        if primary_signal != "Neutral":
            if volume_confirmed and price_confirmed:
                final_signal = f"Strong {primary_signal.split(' ')[0]}" # Strong Bullish/Bearish
            elif volume_confirmed or price_confirmed:
                final_signal = f"Weak {primary_signal.split(' ')[0]}" # Weak Bullish/Bearish
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
