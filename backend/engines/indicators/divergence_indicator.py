import pandas as pd
import logging
from typing import Dict, Any, List, Optional
from .base import BaseIndicator
from .zigzag import ZigzagIndicator
from .rsi import RsiIndicator

logger = logging.getLogger(__name__)

class DivergenceIndicator(BaseIndicator):
    """ Divergence Engine - Definitive, MTF & World-Class Version (v2.1 - Bugfix) """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {}); self.timeframe = self.params.get('timeframe', None)
        self.zigzag_deviation = self.params.get('zigzag_deviation', 3.0)
        self.rsi_period = self.params.get('rsi_period', 14)
        self.lookback_pivots = self.params.get('lookback_pivots', 5)
        self.min_bar_distance = self.params.get('min_bar_distance', 5)
        self._rsi_indicator: Optional[RsiIndicator] = None
        self._zigzag_indicator: Optional[ZigzagIndicator] = None

    def calculate(self) -> 'DivergenceIndicator':
        dependency_params = {'timeframe': self.timeframe}
        
        rsi_params = {'period': self.rsi_period, **dependency_params}
        rsi_instance = RsiIndicator(self.df, params=rsi_params).calculate()
        self.df = rsi_instance.df
        self._rsi_indicator = rsi_instance

        zigzag_params = {'deviation': self.zigzag_deviation, **dependency_params}
        zigzag_instance = ZigzagIndicator(self.df, params=zigzag_params).calculate()
        self.df = zigzag_instance.df
        self._zigzag_indicator = zigzag_instance
        
        return self

    def analyze(self) -> Dict[str, Any]:
        if not self._rsi_indicator or not self._zigzag_indicator: self.calculate()
        pivots_col = self._zigzag_indicator.col_pivots; prices_col = self._zigzag_indicator.col_prices; rsi_col = self._rsi_indicator.rsi_col
        if any(col not in self.df.columns for col in [pivots_col, prices_col, rsi_col]): return {"status": "Error: Missing Dependency Columns", "signals": []}
        pivots_df = self.df[self.df[pivots_col] != 0].copy()
        if len(pivots_df) < 2: return {"status": "OK", "signals": []}
        last_pivot = pivots_df.iloc[-1]
        previous_pivots = pivots_df.iloc[-self.lookback_pivots:-1]
        signals = []
        for i in range(len(previous_pivots)):
            prev_pivot = previous_pivots.iloc[i]
            bar_distance = self.df.index.get_loc(last_pivot.name) - self.df.index.get_loc(prev_pivot.name)
            if bar_distance < self.min_bar_distance: continue
            price1, rsi1 = prev_pivot[prices_col], self.df.loc[prev_pivot.name, rsi_col]
            price2, rsi2 = last_pivot[prices_col], self.df.loc[last_pivot.name, rsi_col]
            divergence = None
            if prev_pivot[pivots_col] == 1 and last_pivot[pivots_col] == 1:
                if price2 > price1 and rsi2 < rsi1: divergence = {"type": "Regular Bearish"}
                if price2 < price1 and rsi2 > rsi1: divergence = {"type": "Hidden Bearish"}
            elif prev_pivot[pivots_col] == -1 and last_pivot[pivots_col] == -1:
                if price2 < price1 and rsi2 > rsi1: divergence = {"type": "Regular Bullish"}
                if price2 > price1 and rsi2 < rsi1: divergence = {"type": "Hidden Bullish"}
            if divergence:
                signals.append({**divergence, "pivots": [{"time": prev_pivot.name.strftime('%Y-%m-%d %H:%M:%S'), "price": round(price1, 5), "rsi": round(rsi1, 2)}, {"time": last_pivot.name.strftime('%Y-%m-%d %H:%M:%S'), "price": round(price2, 5), "rsi": round(rsi2, 2)}]})
        return {"status": "OK", "signals": signals, "timeframe": self.timeframe or 'Base'}
