import pandas as pd
import numpy as np
import logging
from typing import Dict, Any
from .base import BaseIndicator
from .atr import AtrIndicator

logger = logging.getLogger(__name__)

class DonchianChannelIndicator(BaseIndicator):
    """ Donchian Channel - Definitive, MTF & World-Class Version (v2.1 - Bugfix) """
    def __init__(self, df: pd.DataFrame, **kwargs):
        # ... (بخش init بدون تغییر باقی می‌ماند) ...
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
        self.atr_col = f'atr_{self.atr_period}'
        if self.timeframe: self.atr_col += f'_{self.timeframe}'

    def calculate(self) -> 'DonchianChannelIndicator':
        base_df = self.df
        if self.timeframe:
            # ... (Standard MTF Resampling) ...
            rules = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}
            calc_df = base_df.resample(self.timeframe, label='right', closed='right').apply(rules).dropna()
        else:
            calc_df = base_df.copy()

        if len(calc_df) < self.period: logger.warning(f"Not enough data for Donchian on {self.timeframe or 'base'}."); return self

        # ✨ FIX: Correctly handle the return from AtrIndicator.calculate()
        if self.use_atr_filter:
            atr_params = {'period': self.atr_period, 'timeframe': None}
            atr_instance = AtrIndicator(calc_df, params=atr_params).calculate()
            calc_df = atr_instance.df # calc_df now has the atr column

        upper_band = calc_df['high'].rolling(window=self.period).max()
        lower_band = calc_df['low'].rolling(window=self.period).min()
        middle_band = (upper_band + lower_band) / 2
        
        results_df = pd.DataFrame(index=calc_df.index)
        results_df[self.upper_col] = upper_band
        results_df[self.lower_col] = lower_band
        results_df[self.middle_col] = middle_band
        if self.use_atr_filter: results_df[self.atr_col] = calc_df[self.atr_col]

        if self.timeframe:
            # ... (Standard MTF Map Back) ...
            final_results = results_df.reindex(base_df.index, method='ffill')
            for col in final_results.columns: self.df[col] = final_results[col]
        else:
            for col in results_df.columns: self.df[col] = results_df[col]
            
        return self

    def analyze(self) -> Dict[str, Any]:
        # ... (بخش analyze بدون تغییر باقی می‌ماند) ...
        required_cols = [self.upper_col, self.lower_col, 'close']
        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 2: return {"status": "Insufficient Data", "analysis": {}}
        last = valid_df.iloc[-1]; prev = valid_df.iloc[-2]
        signal, message = "Neutral", "Price is inside the channel."
        if last['close'] > prev[self.upper_col]: signal, message = "Buy", "Price closed above the previous upper band."
        elif last['close'] < prev[self.lower_col]: signal, message = "Sell", "Price closed below the previous lower band."
        atr_filter_passed, last_atr_val = True, None
        if self.use_atr_filter and signal != "Neutral":
            if self.atr_col in last and pd.notna(last[self.atr_col]):
                last_atr_val = last[self.atr_col]
                atr_threshold = last['close'] * 0.005 
                if last_atr_val < atr_threshold: atr_filter_passed, message, signal = False, message + " (Signal Ignored: Low Volatility)", "Neutral"
            else: atr_filter_passed, message, signal = False, message + " (Signal Ignored: ATR data missing)", "Neutral"
        return { "status": "OK", "timeframe": self.timeframe or 'Base', "values": { "upper_band": round(last[self.upper_col], 5), "middle_band": round(last[self.middle_col], 5), "lower_band": round(last[self.lower_col], 5), "atr": round(last_atr_val, 5) if last_atr_val is not None else None }, "analysis": { "signal": signal, "message": message, "atr_filter_passed": atr_filter_passed } }

