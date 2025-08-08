import pandas as pd
import numpy as np
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class ZigzagIndicator(BaseIndicator):
    """
    ZigZag Indicator - Definitive MTF & World-Class Market Structure Analysis Tool
    ---------------------------------------------------------------------------------
    This is the final, unified version combining the full market structure analysis
    logic with the multi-timeframe (MTF) architectural pattern.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        # --- Parameters ---
        self.params = kwargs.get('params', {})
        self.deviation = float(self.params.get('deviation', 3.0))
        self.timeframe = self.params.get('timeframe', None)

        # --- Column Naming (Dynamic based on params) ---
        suffix = f'_{self.deviation}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.col_pivots = f'zigzag_pivots{suffix}'
        self.col_prices = f'zigzag_prices{suffix}'

    def _validate_input(self, df: pd.DataFrame) -> pd.DataFrame:
        """Validates the input DataFrame."""
        required_cols = {'high', 'low', 'close'}
        if not required_cols.issubset(df.columns):
            missing = required_cols - set(df.columns)
            msg = f"Missing required columns for ZigZag: {missing}"
            logger.error(msg)
            raise ValueError(msg)
        
        if len(df) < 3:
            logger.warning("ZigZag calculation may be unreliable: data length < 3.")

        for col in required_cols:
             if not pd.api.types.is_numeric_dtype(df[col]):
                  df[col] = pd.to_numeric(df[col], errors='coerce')
        return df.dropna(subset=required_cols)

    def _get_pivots(self, df: pd.DataFrame, deviation_threshold: float):
        """
        The complete, non-repainting pivot detection logic.
        This method is now run on the (potentially resampled) dataframe.
        """
        highs = df['high'].values
        lows = df['low'].values
        pivots = np.zeros(len(df), dtype=int)
        prices = np.zeros(len(df), dtype=float)
        
        if len(df) == 0: return pivots, prices

        last_pivot_idx = 0
        last_pivot_price = highs[0]
        trend = 0

        for i in range(1, len(df)):
            current_high, current_low = highs[i], lows[i]
            if trend == 0:
                if current_high > last_pivot_price * (1 + deviation_threshold / 100):
                    trend = 1; pivots[last_pivot_idx] = -1; prices[last_pivot_idx] = lows[last_pivot_idx]
                    last_pivot_price = current_high; last_pivot_idx = i
                elif current_low < last_pivot_price * (1 - deviation_threshold / 100):
                    trend = -1; pivots[last_pivot_idx] = 1; prices[last_pivot_idx] = highs[last_pivot_idx]
                    last_pivot_price = current_low; last_pivot_idx = i
            elif trend == 1:
                if current_high > last_pivot_price:
                    last_pivot_price = current_high; last_pivot_idx = i
                elif current_low < last_pivot_price * (1 - deviation_threshold / 100):
                    pivots[last_pivot_idx] = 1; prices[last_pivot_idx] = last_pivot_price
                    trend = -1; last_pivot_price = current_low; last_pivot_idx = i
            elif trend == -1:
                if current_low < last_pivot_price:
                    last_pivot_price = current_low; last_pivot_idx = i
                elif current_high > last_pivot_price * (1 + deviation_threshold / 100):
                    pivots[last_pivot_idx] = -1; prices[last_pivot_idx] = last_pivot_price
                    trend = 1; last_pivot_price = current_high; last_pivot_idx = i
        
        if trend != 0 and pivots[last_pivot_idx] == 0:
            pivots[last_pivot_idx] = trend
            prices[last_pivot_idx] = last_pivot_price
            
        return pivots, prices

    def calculate(self) -> 'ZigzagIndicator':
        base_df = self.df
        
        if self.timeframe:
            if not isinstance(base_df.index, pd.DatetimeIndex):
                raise TypeError("DataFrame index must be a DatetimeIndex for MTF.")
            rules = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}
            calc_df = base_df.resample(self.timeframe).apply(rules).dropna()
        else:
            calc_df = base_df.copy()

        validated_df = self._validate_input(calc_df)
        pivots, prices = self._get_pivots(validated_df, self.deviation)
        
        results_df = pd.DataFrame(index=validated_df.index)
        results_df[self.col_pivots] = pivots
        results_df[self.col_prices] = prices

        if self.timeframe:
            final_results = results_df.reindex(base_df.index, method='ffill')
            self.df[self.col_pivots] = final_results[self.col_pivots].fillna(0).astype(int)
            self.df[self.col_prices] = final_results[self.col_prices].fillna(0)
        else:
            self.df[self.col_pivots] = results_df[self.col_pivots]
            self.df[self.col_prices] = results_df[self.col_prices]

        return self

    def analyze(self) -> dict:
        """
        The complete, deep market structure analysis.
        This method operates on the final dataframe which has the MTF columns.
        """
        pivots_df = self.df[self.df[self.col_pivots] != 0].copy()
        
        if len(pivots_df) < 2:
            return {"status": "Awaiting Pivots", "timeframe": self.timeframe or 'Base'}

        last_pivot = pivots_df.iloc[-1]
        prev_pivot = pivots_df.iloc[-2]
        last_type = 'peak' if last_pivot[self.col_pivots] == 1 else 'trough'
        last_price = last_pivot[self.col_prices]
        current_price = self.df['close'].iloc[-1]
        
        bos_signal = 'None'
        if last_type == 'peak' and current_price > last_price:
            bos_signal = 'Bullish BOS'
        elif last_type == 'trough' and current_price < last_price:
            bos_signal = 'Bearish BOS'

        def to_safe_json(value):
            if hasattr(value, 'strftime'): return value.strftime('%Y-%m-%d %H:%M:%S')
            return str(value)

        return {
            "timeframe": self.timeframe or 'Base',
            "last_pivot": {"type": last_type, "price": round(last_price, 5), "time": to_safe_json(last_pivot.name)},
            "previous_pivot": {"type": 'peak' if prev_pivot[self.col_pivots] == 1 else 'trough', "price": round(prev_pivot[self.col_prices], 5), "time": to_safe_json(prev_pivot.name)},
            "market_structure_signal": bos_signal,
            "signal": "bullish" if last_type == 'trough' else "bearish"
        }
