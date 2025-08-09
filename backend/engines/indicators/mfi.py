import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, List, Optional

# اطمینان حاصل کنید که این اندیکاتورها از فایل‌های مربوطه و در نسخه‌های نهایی خود وارد شده‌اند
from .base import BaseIndicator
from .zigzag import ZigzagIndicator # وابستگی جدید برای تشخیص واگرایی

logger = logging.getLogger(__name__)

class MfiIndicator(BaseIndicator):
    """
    Money Flow Index (MFI) - Definitive, MTF, and Divergence-Detection World-Class Version
    ---------------------------------------------------------------------------------------
    This version is a comprehensive money flow analysis engine. It detects:
    - Extreme Overbought/Oversold conditions.
    - Trend-changing 50-level crossovers.
    - Predictive Regular and Hidden divergences by depending on the ZigZag indicator.
    - Fully integrated with the AiSignalPro MTF architecture.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        # --- MFI Parameters ---
        self.params = kwargs.get('params', {})
        self.period = int(self.params.get('period', 14))
        self.overbought = float(self.params.get('overbought', 80.0))
        self.oversold = float(self.params.get('oversold', 20.0))
        self.extreme_overbought = float(self.params.get('extreme_overbought', 90.0))
        self.extreme_oversold = float(self.params.get('extreme_oversold', 10.0))
        self.timeframe = self.params.get('timeframe', None)
        
        # --- Divergence Detection Parameters ---
        self.detect_divergence = bool(self.params.get('detect_divergence', True))
        self.zigzag_deviation = float(self.params.get('zigzag_deviation', 3.0))
        self.divergence_lookback = int(self.params.get('divergence_lookback', 5))

        # --- Dynamic Column Naming ---
        suffix = f'_{self.period}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.mfi_col = f'mfi{suffix}'
        self._zigzag_indicator: Optional[ZigzagIndicator] = None

    def _calculate_mfi(self, df: pd.DataFrame) -> pd.DataFrame:
        """The core, technically correct MFI calculation logic."""
        res = pd.DataFrame(index=df.index)
        
        tp = (df['high'] + df['low'] + df['close']) / 3
        raw_money_flow = tp * df['volume']
        price_diff = tp.diff(1)
        
        pos_flow = np.where(price_diff > 0, raw_money_flow, 0)
        neg_flow = np.where(price_diff < 0, raw_money_flow, 0)

        pos_mf_sum = pd.Series(pos_flow, index=df.index).rolling(window=self.period).sum()
        neg_mf_sum = pd.Series(neg_flow, index=df.index).rolling(window=self.period).sum()

        money_ratio = pos_mf_sum / neg_mf_sum.replace(0, np.nan)
        res[self.mfi_col] = 100 - (100 / (1 + money_ratio))
        res[self.mfi_col].fillna(50, inplace=True) # MFI starts from 50
        return res

    def calculate(self) -> 'MfiIndicator':
        """Orchestrates the MTF calculation for MFI and its dependencies."""
        base_df = self.df
        
        if self.timeframe:
            if not isinstance(base_df.index, pd.DatetimeIndex): raise TypeError("DatetimeIndex required for MTF.")
            rules = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume':'sum'}
            calc_df = base_df.resample(self.timeframe, label='right', closed='right').apply(rules).dropna()
        else:
            calc_df = base_df.copy()

        if len(calc_df) < self.period: logger.warning(f"Not enough data for MFI on {self.timeframe or 'base'}."); return self

        mfi_results = self._calculate_mfi(calc_df)
        
        # --- Dependency Calculation: ZigZag for Divergence ---
        if self.detect_divergence:
            zigzag_params = {'deviation': self.zigzag_deviation, 'timeframe': None}
            self._zigzag_indicator = ZigzagIndicator(calc_df, params=zigzag_params)
            calc_df = self._zigzag_indicator.calculate()
            # Copy zigzag columns to the results df
            mfi_results[self._zigzag_indicator.col_pivots] = calc_df[self._zigzag_indicator.col_pivots]
            mfi_results[self._zigzag_indicator.col_prices] = calc_df[self._zigzag_indicator.col_prices]

        # --- Map results back to the original dataframe if MTF ---
        if self.timeframe:
            final_results = mfi_results.reindex(base_df.index, method='ffill')
            for col in final_results.columns: self.df[col] = final_results[col]
        else:
            for col in mfi_results.columns: self.df[col] = mfi_results[col]

        return self
    
    def _find_divergences(self, valid_df: pd.DataFrame) -> List[Dict[str, Any]]:
        if not self.detect_divergence or self._zigzag_indicator is None: return []

        pivot_col = self._zigzag_indicator.col_pivots
        price_col = self._zigzag_indicator.col_prices
        pivots_df = valid_df[valid_df[pivot_col] != 0]

        if len(pivots_df) < 2: return []
        
        last_pivot = pivots_df.iloc[-1]
        previous_pivots = pivots_df.iloc[-self.divergence_lookback:-1]
        divergences = []

        for i in range(len(previous_pivots)):
            prev_pivot = previous_pivots.iloc[i]
            
            price1, mfi1 = prev_pivot[price_col], prev_pivot[self.mfi_col]
            price2, mfi2 = last_pivot[price_col], last_pivot[self.mfi_col]

            # Compare two peaks
            if prev_pivot[pivot_col] == 1 and last_pivot[pivot_col] == 1:
                if price2 > price1 and mfi2 < mfi1: divergences.append({'type': 'Regular Bearish'})
                if price2 < price1 and mfi2 > mfi1: divergences.append({'type': 'Hidden Bearish'})
            # Compare two troughs
            elif prev_pivot[pivot_col] == -1 and last_pivot[pivot_col] == -1:
                if price2 < price1 and mfi2 > mfi1: divergences.append({'type': 'Regular Bullish'})
                if price2 > price1 and mfi2 < mfi1: divergences.append({'type': 'Hidden Bullish'})
        
        return divergences

    def analyze(self) -> Dict[str, Any]:
        """Provides a multi-faceted analysis of money flow."""
        valid_df = self.df.dropna(subset=[self.mfi_col])
        if len(valid_df) < 2: return {"status": "Insufficient Data"}

        last = valid_df.iloc[-1]; prev = valid_df.iloc[-2]
        last_mfi = last[self.mfi_col]; prev_mfi = prev[self.mfi_col]

        # --- 1. Positional Analysis ---
        position = "Neutral"
        if last_mfi >= self.extreme_overbought: position = "Extremely Overbought"
        elif last_mfi >= self.overbought: position = "Overbought"
        elif last_mfi <= self.extreme_oversold: position = "Extremely Oversold"
        elif last_mfi <= self.oversold: position = "Oversold"

        # --- 2. Crossover Signal Analysis ---
        signal = "Hold"
        if prev_mfi <= self.oversold and last_mfi > self.oversold: signal = "Oversold Exit (Buy)"
        elif prev_mfi >= self.overbought and last_mfi < self.overbought: signal = "Overbought Exit (Sell)"
        elif prev_mfi <= 50 and last_mfi > 50: signal = "Bullish Centerline Cross"
        elif prev_mfi >= 50 and last_mfi < 50: signal = "Bearish Centerline Cross"
            
        # --- 3. Divergence Analysis ---
        divergences = self._find_divergences(valid_df)
        
        return {
            "status": "OK", "timeframe": self.timeframe or 'Base',
            "values": {"mfi": round(last_mfi, 2)},
            "analysis": {
                "position": position,
                "crossover_signal": signal,
                "divergences": divergences # List of found divergences
            }
        }
