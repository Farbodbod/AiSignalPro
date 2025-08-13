import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, List, Optional

from .base import BaseIndicator
from .zigzag import ZigzagIndicator # For standardized column naming

logger = logging.getLogger(__name__)

class RsiIndicator(BaseIndicator):
    """
    RSI - (v5.0 - Harmonized API & Multi-Version Aware)
    ------------------------------------------------------------------
    This world-class version acts as both a provider and a consumer within the
    Multi-Version Engine. It provides a standardized `get_col_name` method for other
    indicators and intelligently consumes its ZigZag dependency, making it a
    fully harmonized and powerful component of the AiSignalPro ecosystem.
    """
    # ✅ MIRACLE UPGRADE: Dependencies are now declared in config.
    dependencies: list = []

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.period = int(self.params.get('period', 14))
        self.timeframe = self.params.get('timeframe', None)
        self.signal_period = int(self.params.get('signal_period', 9))
        self.use_dynamic_levels = bool(self.params.get('use_dynamic_levels', True))
        self.bb_period = int(self.params.get('bb_period', 20))
        self.bb_std_dev = float(self.params.get('bb_std_dev', 2.0))
        self.detect_divergence = bool(self.params.get('detect_divergence', True))
        self.divergence_lookback = int(self.params.get('lookback_pivots', 5)) # Harmonized name

        # ✅ MIRACLE UPGRADE: The indicator now reads its specific dependency config.
        self.zigzag_dependency_params = self.params.get('dependencies', {}).get('zigzag', {'deviation': 3.0})

        # ✅ HARMONIZED: Column names are now generated using the official static method
        self.rsi_col = RsiIndicator.get_col_name(self.params, self.timeframe)
        self.rsi_signal_col = f'rsi_signal_{self.signal_period}{self.rsi_col[3:]}' # Append to base rsi name
        self.dyn_upper_col = f'rsi_dyn_upper_{self.bb_period}{self.rsi_col[3:]}'
        self.dyn_lower_col = f'rsi_dyn_lower_{self.bb_period}{self.rsi_col[3:]}'

    @staticmethod
    def get_col_name(params: Dict[str, Any], timeframe: Optional[str] = None) -> str:
        """ ✅ NEW: The official, standardized method for generating the RSI column name. """
        period = params.get('period', 14)
        name = f'rsi_{period}'
        if timeframe:
            name += f'_{timeframe}'
        return name

    def calculate(self) -> 'RsiIndicator':
        """ Calculates RSI and its related metrics. """
        df_for_calc = self.df
        
        if len(df_for_calc) < max(self.period, self.bb_period):
            logger.warning(f"Not enough data for RSI on {self.timeframe or 'base'}.")
            for col in [self.rsi_col, self.rsi_signal_col, self.dyn_upper_col, self.dyn_lower_col]:
                if hasattr(self, col): self.df[col] = np.nan
            return self

        delta = df_for_calc['close'].diff()
        gain = delta.where(delta > 0, 0).ewm(alpha=1/self.period, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/self.period, adjust=False).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        self.df[self.rsi_col] = rsi

        self.df[self.rsi_signal_col] = rsi.ewm(span=self.signal_period, adjust=False).mean()
        
        if self.use_dynamic_levels:
            rsi_ma = rsi.rolling(window=self.bb_period).mean()
            rsi_std = rsi.rolling(window=self.bb_period).std(ddof=0)
            self.df[self.dyn_upper_col] = rsi_ma + (rsi_std * self.bb_std_dev)
            self.df[self.dyn_lower_col] = rsi_ma - (rsi_std * self.bb_std_dev)
            
        return self
    
    def _find_divergences(self, valid_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """ Finds divergences by consuming pre-calculated ZigZag columns via the new contract. """
        if not self.detect_divergence: return []

        # ✅ MIRACLE UPGRADE: Gets column names from the ZigZag indicator's contract
        pivot_col = ZigzagIndicator.get_pivots_col_name(self.zigzag_dependency_params, self.timeframe)
        price_col = ZigzagIndicator.get_prices_col_name(self.zigzag_dependency_params, self.timeframe)
        
        if not all(col in valid_df.columns for col in [pivot_col, price_col]):
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
            divergence = None
            if prev_pivot[pivot_col] == 1 and last_pivot[pivot_col] == 1:
                if price2 > price1 and rsi2 < rsi1: divergences.append({'type': 'Regular Bearish'})
                if price2 < price1 and rsi2 > rsi1: divergences.append({'type': 'Hidden Bearish'})
            elif prev_pivot[pivot_col] == -1 and last_pivot[pivot_col] == -1:
                if price2 < price1 and rsi2 > rsi1: divergences.append({'type': 'Regular Bullish'})
                if price2 > price1 and rsi2 < rsi1: divergences.append({'type': 'Hidden Bullish'})
        return divergences

    def analyze(self) -> Dict[str, Any]:
        """ Provides a multi-dimensional analysis of RSI. """
        required = [self.rsi_col, self.rsi_signal_col]
        if self.use_dynamic_levels: required.extend([self.dyn_upper_col, self.dyn_lower_col])
        valid_df = self.df.dropna(subset=required)
        if len(valid_df) < 2: return {"status": "Insufficient Data"}

        last = valid_df.iloc[-1]; prev = valid_df.iloc[-2]
        last_rsi = last[self.rsi_col]

        ob_level = last.get(self.dyn_upper_col, self.params.get('overbought', 70.0))
        os_level = last.get(self.dyn_lower_col, self.params.get('oversold', 30.0))
        
        position = "Neutral"
        if last_rsi > ob_level: position = "Overbought"
        elif last_rsi < os_level: position = "Oversold"
            
        signals = []
        if prev[self.rsi_col] <= 50 and last_rsi > 50: signals.append("Bullish Centerline Cross")
        if prev[self.rsi_col] >= 50 and last_rsi < 50: signals.append("Bearish Centerline Cross")
        if prev[self.rsi_col] <= prev[self.rsi_signal_col] and last_rsi > last[self.rsi_signal_col]: signals.append("Bullish Signal Line Cross")
        if prev[self.rsi_col] >= prev[self.rsi_signal_col] and last_rsi < last[self.rsi_signal_col]: signals.append("Bearish Signal Line Cross")

        divergences = self._find_divergences(valid_df)
        
        return {
            "status": "OK", "timeframe": self.timeframe or 'Base',
            "values": {"rsi": round(last_rsi, 2), "signal_line": round(last[self.rsi_signal_col], 2)},
            "levels": {"overbought": round(ob_level, 2), "oversold": round(os_level, 2), "is_dynamic": self.use_dynamic_levels},
            "analysis": { "position": position, "crossover_signals": signals, "divergences": divergences }
        }
