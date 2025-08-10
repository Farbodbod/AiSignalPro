import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class DonchianChannelIndicator(BaseIndicator):
    """
    Donchian Channel - Definitive, MTF & World-Class Version (v3.0 - No Internal Deps)
    ----------------------------------------------------------------------------------
    This version adheres to the final AiSignalPro architecture. It does not
    calculate its own dependencies. Instead, its analyze() method consumes the
    pre-calculated ATR column provided by the IndicatorAnalyzer for its optional
    volatility filter.
    """
    dependencies = ['atr']

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.period = int(self.params.get('period', 20))
        self.timeframe = self.params.get('timeframe', None)
        self.use_atr_filter = bool(self.params.get('use_atr_filter', False))
        self.atr_period = int(self.params.get('atr_period', 14))
        
        suffix = f'_{self.period}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.upper_col = f'donchian_upper{suffix}'
        self.lower_col = f'donchian_lower{suffix}'
        self.middle_col = f'donchian_middle{suffix}'

    def calculate(self) -> 'DonchianChannelIndicator':
        """
        Calculates the Donchian Channel bands. It no longer calculates ATR internally.
        """
        base_df = self.df
        if self.timeframe:
            rules = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}
            calc_df = base_df.resample(self.timeframe, label='right', closed='right').apply(rules).dropna()
        else:
            calc_df = base_df.copy()
        
        if len(calc_df) < self.period:
            logger.warning(f"Not enough data for Donchian on {self.timeframe or 'base'}.")
            self.df[self.upper_col] = np.nan; self.df[self.lower_col] = np.nan; self.df[self.middle_col] = np.nan
            return self

        # --- Core Donchian Calculation ---
        upper_band = calc_df['high'].rolling(window=self.period).max()
        lower_band = calc_df['low'].rolling(window=self.period).min()
        middle_band = (upper_band + lower_band) / 2
        
        results_df = pd.DataFrame(index=calc_df.index)
        results_df[self.upper_col] = upper_band
        results_df[self.lower_col] = lower_band
        results_df[self.middle_col] = middle_band

        # --- Map results back to the original dataframe if MTF ---
        if self.timeframe:
            final_results = results_df.reindex(base_df.index, method='ffill')
            self.df[self.upper_col] = final_results[self.upper_col]
            self.df[self.lower_col] = final_results[self.lower_col]
            self.df[self.middle_col] = final_results[self.middle_col]
        else:
            self.df[self.upper_col] = results_df[self.upper_col]
            self.df[self.lower_col] = results_df[self.lower_col]
            self.df[self.middle_col] = results_df[self.middle_col]
            
        return self

    def analyze(self) -> Dict[str, Any]:
        """
        Analyzes for breakouts, applying an ATR filter if configured and available.
        """
        required_cols = [self.upper_col, self.lower_col, 'close']
        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 2:
            return {"status": "Insufficient Data", "analysis": {}}

        last = valid_df.iloc[-1]; prev = valid_df.iloc[-2]
        
        signal, message = "Neutral", "Price is inside the channel."
        if last['close'] > prev[self.upper_col]:
            signal, message = "Buy", "Price closed above the previous upper band."
        elif last['close'] < prev[self.lower_col]:
            signal, message = "Sell", "Price closed below the previous lower band."

        # --- ✨ FINAL ARCHITECTURE: ATR Filter (Consumer Logic) ---
        atr_filter_passed, last_atr_val = True, None
        if self.use_atr_filter and signal != "Neutral":
            atr_col_name = f'atr_{self.atr_period}'
            if self.timeframe: atr_col_name += f'_{self.timeframe}'
            
            if atr_col_name in last and pd.notna(last[atr_col_name]):
                last_atr_val = last[atr_col_name]
                # A simple volatility threshold: e.g., breakout is only valid if ATR is at least 0.5% of the price
                atr_threshold = last['close'] * 0.005 
                if last_atr_val < atr_threshold:
                    atr_filter_passed, message, signal = False, message + " (Signal Ignored: Low Volatility)", "Neutral"
            else:
                # If the column is not found, the filter fails.
                atr_filter_passed, message, signal = False, message + f" (Signal Ignored: ATR column '{atr_col_name}' missing)", "Neutral"
        
        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "values": {
                "upper_band": round(last[self.upper_col], 5),
                "middle_band": round(last[self.middle_col], 5),
                "lower_band": round(last[self.lower_col], 5),
                "atr_for_filter": round(last_atr_val, 5) if last_atr_val is not None else None
            },
            "analysis": {
                "signal": signal,
                "message": message,
                "atr_filter_passed": atr_filter_passed
            }
        }
