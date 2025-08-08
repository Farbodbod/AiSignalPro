import pandas as pd
import logging
from typing import Dict, Any, List, Optional

from .base import BaseIndicator
from .zigzag import ZigzagIndicator # نسخه کامل MTF
from .rsi import RsiIndicator      # نسخه کامل MTF

logger = logging.getLogger(__name__)

class DivergenceIndicator(BaseIndicator):
    """
    Divergence Analysis Engine - Definitive, Complete, MTF & World-Class Version
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.timeframe = self.params.get('timeframe', None)
        self.zigzag_deviation = self.params.get('zigzag_deviation', 3.0)
        self.rsi_period = self.params.get('rsi_period', 14)
        self.lookback_pivots = self.params.get('lookback_pivots', 5)
        self.min_bar_distance = self.params.get('min_bar_distance', 5)
        self.overbought = self.params.get('overbought', 68)
        self.oversold = self.params.get('oversold', 32)
        
        self._rsi_indicator: Optional[RsiIndicator] = None
        self._zigzag_indicator: Optional[ZigzagIndicator] = None

    def calculate(self) -> 'DivergenceIndicator':
        dependency_params = {'timeframe': self.timeframe}
        rsi_params = {'period': self.rsi_period, **dependency_params}
        self._rsi_indicator = RsiIndicator(self.df, params=rsi_params)
        self.df = self._rsi_indicator.calculate()

        zigzag_params = {'deviation': self.zigzag_deviation, **dependency_params}
        self._zigzag_indicator = ZigzagIndicator(self.df, params=zigzag_params)
        self.df = self._zigzag_indicator.calculate()
        return self

    def _check_divergence_pair(self, pivot1: pd.Series, pivot2: pd.Series) -> Optional[Dict[str, Any]]:
        prices_col = self._zigzag_indicator.col_prices
        pivots_col = self._zigzag_indicator.col_pivots
        rsi_col = self._rsi_indicator.rsi_col
        
        price1, rsi1 = pivot1[prices_col], self.df.loc[pivot1.name, rsi_col]
        price2, rsi2 = pivot2[prices_col], self.df.loc[pivot2.name, rsi_col]

        if pivot1[pivots_col] == 1 and pivot2[pivots_col] == 1:
            if price2 > price1 and rsi2 < rsi1: return {"type": "Regular Bearish", "strength": "Strong" if rsi2 > self.overbought else "Normal"}
            if price2 < price1 and rsi2 > rsi1: return {"type": "Hidden Bearish", "strength": "Continuation Signal"}
        elif pivot1[pivots_col] == -1 and pivot2[pivots_col] == -1:
            if price2 < price1 and rsi2 > rsi1: return {"type": "Regular Bullish", "strength": "Strong" if rsi2 < self.oversold else "Normal"}
            if price2 > price1 and rsi2 < rsi1: return {"type": "Hidden Bullish", "strength": "Continuation Signal"}
        return None

    def analyze(self) -> Dict[str, Any]:
        if not self._rsi_indicator or not self._zigzag_indicator: self.calculate()
            
        pivots_col = self._zigzag_indicator.col_pivots
        prices_col = self._zigzag_indicator.col_prices
        rsi_col = self._rsi_indicator.rsi_col

        if any(c not in self.df.columns for c in [pivots_col, prices_col, rsi_col]):
            return {"status": "Error: Missing Dependencies", "signals": []}

        pivots_df = self.df[self.df[pivots_col] != 0].copy()
        if len(pivots_df) < 2: return {"status": "OK", "signals": []}

        last_pivot = pivots_df.iloc[-1]
        previous_pivots = pivots_df.iloc[-self.lookback_pivots:-1]
        signals = []

        for i in range(len(previous_pivots)):
            prev_pivot = previous_pivots.iloc[i]
            bar_distance = self.df.index.get_loc(last_pivot.name) - self.df.index.get_loc(prev_pivot.name)
            if bar_distance < self.min_bar_distance: continue

            divergence = self._check_divergence_pair(prev_pivot, last_pivot)
            if divergence:
                signals.append({**divergence, "pivots": [
                    {"time": prev_pivot.name.strftime('%Y-%m-%d %H:%M:%S'), "price": round(prev_pivot[prices_col], 5), "rsi": round(self.df.loc[prev_pivot.name, rsi_col], 2)},
                    {"time": last_pivot.name.strftime('%Y-%m-%d %H:%M:%S'), "price": round(last_pivot[prices_col], 5), "rsi": round(self.df.loc[last_pivot.name, rsi_col], 2)}
                ]})
        return {"status": "OK", "signals": signals, "timeframe": self.timeframe or 'Base'}
