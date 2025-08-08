import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

# اطمینان حاصل کنید که این اندیکاتور از فایل مربوطه وارد شده‌ است
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class IchimokuIndicator(BaseIndicator):
    """
    Ichimoku Kinko Hyo - Definitive, Complete, MTF & World-Class Version
    ----------------------------------------------------------------------
    This version implements the full Ichimoku system with the standardized
    MTF architecture of the AiSignalPro project. It provides a comprehensive
    analysis of trend, momentum, and future support/resistance zones.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        # --- Parameters ---
        self.params = kwargs.get('params', {})
        self.tenkan_period = int(self.params.get('tenkan_period', 9))
        self.kijun_period = int(self.params.get('kijun_period', 26))
        self.senkou_b_period = int(self.params.get('senkou_b_period', 52))
        # For clarity: chikou_span is the close shifted BACK by this period
        self.chikou_shift = int(self.params.get('chikou_shift', 26))
        # For clarity: senkou spans are shifted FORWARD by this period
        self.senkou_lead = int(self.params.get('senkou_lead', 26))
        self.timeframe = self.params.get('timeframe', None)

        # --- Dynamic Column Naming ---
        suffix = f'_{self.tenkan_period}_{self.kijun_period}_{self.senkou_b_period}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.tenkan_col = f'ichi_tenkan{suffix}'
        self.kijun_col = f'ichi_kijun{suffix}'
        self.chikou_col = f'ichi_chikou{suffix}'
        self.senkou_a_col = f'ichi_senkou_a{suffix}'
        self.senkou_b_col = f'ichi_senkou_b{suffix}'

    def _calculate_ichimoku(self, df: pd.DataFrame) -> pd.DataFrame:
        """The core, NaN-safe Ichimoku calculation logic."""
        res = pd.DataFrame(index=df.index)
        
        # Tenkan-sen (Conversion Line)
        tenkan_high = df['high'].rolling(window=self.tenkan_period).max()
        tenkan_low = df['low'].rolling(window=self.tenkan_period).min()
        res[self.tenkan_col] = (tenkan_high + tenkan_low) / 2

        # Kijun-sen (Base Line)
        kijun_high = df['high'].rolling(window=self.kijun_period).max()
        low_kijun = df['low'].rolling(window=self.kijun_period).min()
        res[self.kijun_col] = (kijun_high + low_kijun) / 2

        # Senkou Span A (Leading Span A)
        res[self.senkou_a_col] = ((res[self.tenkan_col] + res[self.kijun_col]) / 2).shift(self.senkou_lead)

        # Senkou Span B (Leading Span B)
        senkou_b_high = df['high'].rolling(window=self.senkou_b_period).max()
        senkou_b_low = df['low'].rolling(window=self.senkou_b_period).min()
        res[self.senkou_b_col] = ((senkou_b_high + senkou_b_low) / 2).shift(self.senkou_lead)

        # Chikou Span (Lagging Span)
        res[self.chikou_col] = df['close'].shift(-self.chikou_shift)
        
        return res

    def calculate(self) -> 'IchimokuIndicator':
        """Orchestrates the MTF calculation for Ichimoku."""
        base_df = self.df
        
        if self.timeframe:
            if not isinstance(base_df.index, pd.DatetimeIndex):
                raise TypeError("DataFrame index must be a DatetimeIndex for MTF.")
            rules = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}
            calc_df = base_df.resample(self.timeframe, label='right', closed='right').apply(rules).dropna()
        else:
            calc_df = base_df.copy()

        if len(calc_df) < self.senkou_b_period:
            logger.warning(f"Not enough data for Ichimoku on timeframe {self.timeframe or 'base'}.")
            return self

        ichimoku_results = self._calculate_ichimoku(calc_df)
        
        # --- Map results back to the original dataframe if MTF ---
        if self.timeframe:
            final_results = ichimoku_results.reindex(base_df.index, method='ffill')
            for col in final_results.columns: self.df[col] = final_results[col]
        else:
            for col in ichimoku_results.columns: self.df[col] = ichimoku_results[col]

        return self

    def analyze(self) -> Dict[str, Any]:
        """Provides a comprehensive analysis of the Ichimoku signals."""
        required_cols = [self.tenkan_col, self.kijun_col, self.senkou_a_col, self.senkou_b_col, self.chikou_col]
        if any(col not in self.df.columns for col in required_cols) or self.df[self.tenkan_col].isnull().all():
            return {"status": "No Data", "analysis": {}}

        # Use last valid non-NaN index for analysis to avoid issues at the start
        last_valid_idx = self.df[self.tenkan_col].last_valid_index()
        if last_valid_idx is None or self.df.index.get_loc(last_valid_idx) < 1:
             return {"status": "Insufficient Data", "analysis": {}}

        last = self.df.loc[last_valid_idx]
        prev = self.df.loc[self.df.index[self.df.index.get_loc(last_valid_idx) - 1]]

        # --- 1. Kumo (Cloud) Analysis ---
        kumo_top = max(last[self.senkou_a_col], last[self.senkou_b_col])
        kumo_bottom = min(last[self.senkou_a_col], last[self.senkou_b_col])
        price_pos = "Inside Kumo"
        if last['close'] > kumo_top: price_pos = "Above Kumo"
        elif last['close'] < kumo_bottom: price_pos = "Below Kumo"
            
        # --- 2. Tenkan/Kijun (TK) Cross Analysis ---
        tk_cross = "Neutral"
        if prev[self.tenkan_col] < prev[self.kijun_col] and last[self.tenkan_col] > last[self.kijun_col]:
            tk_cross = "Weak Bullish" if price_pos == "Below Kumo" else "Strong Bullish"
        elif prev[self.tenkan_col] > prev[self.kijun_col] and last[self.tenkan_col] < last[self.kijun_col]:
            tk_cross = "Weak Bearish" if price_pos == "Above Kumo" else "Strong Bearish"

        # --- 3. Chikou Span Confirmation ---
        chikou_conf = "Neutral"
        # Correctly get the price at the time the Chikou span represents
        chikou_time_idx = self.df.index.get_loc(last_valid_idx) - self.chikou_shift
        if chikou_time_idx >= 0:
            past_price = self.df['close'].iloc[chikou_time_idx]
            if last[self.chikou_col] > past_price: chikou_conf = "Bullish"
            elif last[self.chikou_col] < past_price: chikou_conf = "Bearish"

        # --- 4. Final Aggregated Signal ---
        trend = "Neutral"
        if price_pos == "Above Kumo" and tk_cross.endswith("Bullish") and chikou_conf == "Bullish":
            trend = "Strong Bullish"
        elif price_pos == "Below Kumo" and tk_cross.endswith("Bearish") and chikou_conf == "Bearish":
            trend = "Strong Bearish"
        elif price_pos == "Above Kumo": trend = "Bullish Trend"
        elif price_pos == "Below Kumo": trend = "Bearish Trend"
        
        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "values": {
                "tenkan": round(last[self.tenkan_col], 5), "kijun": round(last[self.kijun_col], 5),
                "senkou_a": round(last[self.senkou_a_col], 5), "senkou_b": round(last[self.senkou_b_col], 5)
            },
            "analysis": {
                "trend": trend,
                "price_position": price_pos,
                "tk_cross": tk_cross,
                "chikou_confirmation": chikou_conf
            }
        }
