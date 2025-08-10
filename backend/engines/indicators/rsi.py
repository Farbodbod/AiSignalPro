import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, List, Optional

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class RsiIndicator(BaseIndicator):
    """
    RSI - Definitive, Multi-Signal, MTF & World-Class Version (v3.0 - No Internal Deps)
    ------------------------------------------------------------------------------------
    This is a comprehensive momentum analysis engine based on RSI, featuring a smoothed
    signal line, dynamic Bollinger Bands for OB/OS levels, and predictive divergence
    detection by consuming pre-calculated ZigZag columns.
    """
    dependencies = ['zigzag']

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.period = int(self.params.get('period', 14))
        self.timeframe = self.params.get('timeframe', None)
        self.signal_period = int(self.params.get('signal_period', 5))
        self.use_dynamic_levels = bool(self.params.get('use_dynamic_levels', True))
        self.bb_period = int(self.params.get('bb_period', 20))
        self.bb_std_dev = float(self.params.get('bb_std_dev', 2.0))
        self.fixed_overbought = float(self.params.get('overbought', 70.0))
        self.fixed_oversold = float(self.params.get('oversold', 30.0))
        self.detect_divergence = bool(self.params.get('detect_divergence', True))
        self.zigzag_deviation = float(self.params.get('zigzag_deviation', 3.0))
        self.divergence_lookback = int(self.params.get('divergence_lookback', 5))

        suffix = f'_{self.period}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.rsi_col = f'rsi{suffix}'
        self.rsi_signal_col = f'rsi_signal_{self.signal_period}{suffix}'
        self.dyn_upper_col = f'rsi_dyn_upper_{self.bb_period}{suffix}'
        self.dyn_lower_col = f'rsi_dyn_lower_{self.bb_period}{suffix}'

    def _calculate_rsi_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        """The core logic for calculating RSI and its related metrics (signal line, dynamic bands)."""
        res = pd.DataFrame(index=df.index)
        close = pd.to_numeric(df['close'], errors='coerce')
        
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).ewm(alpha=1/self.period, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/self.period, adjust=False).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        res[self.rsi_col] = rsi

        res[self.rsi_signal_col] = rsi.ewm(span=self.signal_period, adjust=False).mean()
        
        if self.use_dynamic_levels:
            rsi_ma = rsi.rolling(window=self.bb_period).mean()
            rsi_std = rsi.rolling(window=self.bb_period).std(ddof=0)
            res[self.dyn_upper_col] = rsi_ma + (rsi_std * self.bb_std_dev)
            res[self.dyn_lower_col] = rsi_ma - (rsi_std * self.bb_std_dev)
            
        return res

    def calculate(self) -> 'RsiIndicator':
        """Calculates RSI and its metrics, assuming ZigZag is pre-calculated if needed."""
        base_df = self.df
        if self.timeframe:
            rules = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}
            calc_df = base_df.resample(self.timeframe, label='right', closed='right').apply(rules).dropna()
        else:
            calc_df = base_df.copy()
            
        if len(calc_df) < max(self.period, self.bb_period):
            logger.warning(f"Not enough data for RSI on {self.timeframe or 'base'}.")
            return self

        rsi_results = self._calculate_rsi_metrics(calc_df)
        
        if self.timeframe:
            final_results = rsi_results.reindex(base_df.index, method='ffill')
            for col in final_results.columns: self.df[col] = final_results[col]
        else:
            for col in rsi_results.columns: self.df[col] = rsi_results[col]
            
        return self
    
    def _find_divergences(self, valid_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Finds divergences by consuming pre-calculated ZigZag columns."""
        if not self.detect_divergence: return []

        tf_suffix = f'_{self.timeframe}' if self.timeframe else ''
        pivot_col = f'zigzag_pivots_{self.zigzag_deviation}{tf_suffix}'
        price_col = f'zigzag_prices_{self.zigzag_deviation}{tf_suffix}'
        
        if not all(col in valid_df.columns for col in [pivot_col, price_col]):
             logger.warning(f"[{self.__class__.__name__}] ZigZag columns not found for divergence detection.")
             return []

        pivots_df = valid_df[valid_df[pivot_col] != 0]
        if len(pivots_df) < 2: return []
        
        last_pivot = pivots_df.iloc[-1]
        previous_pivots = pivots_df.iloc[-self.divergence_lookback:-1]
        divergences = []

        for i in range(len(previous_pivots)):
            prev_pivot = previous_pivots.iloc[i]
            price1, rsi1 = prev_pivot[price_col], prev_pivot[self.rsi_col]
            price2, rsi2 = last_pivot[price_col], last_pivot[self.rsi_col]
            if prev_pivot[pivot_col] == 1 and last_pivot[pivot_col] == 1:
                if price2 > price1 and rsi2 < rsi1: divergences.append({'type': 'Regular Bearish'})
                if price2 < price1 and rsi2 > rsi1: divergences.append({'type': 'Hidden Bearish'})
            elif prev_pivot[pivot_col] == -1 and last_pivot[pivot_col] == -1:
                if price2 < price1 and rsi2 > rsi1: divergences.append({'type': 'Regular Bullish'})
                if price2 > price1 and rsi2 < rsi1: divergences.append({'type': 'Hidden Bullish'})
        return divergences

    def analyze(self) -> Dict[str, Any]:
        """Provides a multi-dimensional analysis of RSI."""
        required = [self.rsi_col, self.rsi_signal_col]
        if self.use_dynamic_levels: required.extend([self.dyn_upper_col, self.dyn_lower_col])
        valid_df = self.df.dropna(subset=required)
        if len(valid_df) < 2: return {"status": "Insufficient Data"}

        last = valid_df.iloc[-1]; prev = valid_df.iloc[-2]
        last_rsi = last[self.rsi_col]

        ob_level = last[self.dyn_upper_col] if self.use_dynamic_levels else self.fixed_overbought
        os_level = last[self.dyn_lower_col] if self.use_dynamic_levels else self.fixed_oversold
        
        position = "Neutral"
        if last_rsi > ob_level: position = "Overbought"
        elif last_rsi < os_level: position = "Oversold"
            
        signals = []
        if prev[self.rsi_col] <= os_level and last_rsi > os_level: signals.append("Oversold Exit")
        if prev[self.rsi_col] >= ob_level and last_rsi < ob_level: signals.append("Overbought Exit")
        if prev[self.rsi_col] <= 50 and last_rsi > 50: signals.append("Bullish Centerline Cross")
        if prev[self.rsi_col] >= 50 and last_rsi < 50: signals.append("Bearish Centerline Cross")
        if prev[self.rsi_col] <= prev[self.rsi_signal_col] and last_rsi > last[self.rsi_signal_col]: signals.append("Bullish Signal Line Cross")
        if prev[self.rsi_col] >= prev[self.rsi_signal_col] and last_rsi < last[self.rsi_signal_col]: signals.append("Bearish Signal Line Cross")

        divergences = self._find_divergences(valid_df)
        
        return {
            "status": "OK", "timeframe": self.timeframe or 'Base',
            "values": {"rsi": round(last_rsi, 2), "signal_line": round(last[self.rsi_signal_col], 2)},
            "levels": {"overbought": round(ob_level, 2), "oversold": round(os_level, 2), "is_dynamic": self.use_dynamic_levels},
            "analysis": {
                "position": position,
                "crossover_signals": signals,
                "divergences": divergences
            }
        }
