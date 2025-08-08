import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

# اطمینان حاصل کنید که این اندیکاتورها از فایل‌های مربوطه و در نسخه‌های نهایی خود وارد شده‌اند
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class AtrIndicator(BaseIndicator):
    """
    ATR Indicator - Definitive, Complete, MTF & World-Class Version
    ----------------------------------------------------------------
    This is the final, unified version combining intelligent volatility
    analysis with the multi-timeframe (MTF) architectural pattern.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        # --- Parameters ---
        self.params = kwargs.get('params', {})
        self.period = int(self.params.get('period', 14))
        self.timeframe = self.params.get('timeframe', None)
        self.volatility_thresholds = self.params.get('volatility_thresholds', {
            'low_max': 1.0,   # ATR percent below this is "Low"
            'normal_max': 3.0, # ATR percent below this is "Normal"
            'high_max': 5.0    # ATR percent below this is "High", above is "Extreme"
        })

        # --- Dynamic Column Naming ---
        suffix = f'_{self.period}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.atr_col = f'atr{suffix}'
        self.atr_pct_col = f'atr_pct{suffix}'

    def calculate(self) -> 'AtrIndicator':
        """Calculates ATR and Normalized ATR, handling MTF internally."""
        base_df = self.df
        
        # ✨ MTF LOGIC: Resample
        if self.timeframe:
            if not isinstance(base_df.index, pd.DatetimeIndex):
                raise TypeError("DataFrame index must be a DatetimeIndex for MTF.")
            rules = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}
            calc_df = base_df.resample(self.timeframe).apply(rules).dropna()
        else:
            calc_df = base_df.copy()

        if len(calc_df) < self.period:
            logger.warning(f"Not enough data for ATR on timeframe {self.timeframe or 'base'}.")
            self.df[self.atr_col] = np.nan
            self.df[self.atr_pct_col] = np.nan
            return self
            
        # --- Vectorized Calculation on calc_df ---
        tr = pd.concat([
            calc_df['high'] - calc_df['low'],
            np.abs(calc_df['high'] - calc_df['close'].shift(1)),
            np.abs(calc_df['low'] - calc_df['close'].shift(1))
        ], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1/self.period, adjust=False).mean()
        
        safe_close = calc_df['close'].replace(0, np.nan)
        atr_pct = (atr / safe_close) * 100
        
        # --- Map results back to the original dataframe if MTF ---
        results_df = pd.DataFrame(index=calc_df.index)
        results_df[self.atr_col] = atr
        results_df[self.atr_pct_col] = atr_pct

        if self.timeframe:
            final_results = results_df.reindex(base_df.index, method='ffill')
            self.df[self.atr_col] = final_results[self.atr_col]
            self.df[self.atr_pct_col] = final_results[self.atr_pct_col]
        else:
            self.df[self.atr_col] = results_df[self.atr_col]
            self.df[self.atr_pct_col] = results_df[self.atr_pct_col]
        
        return self

    def analyze(self) -> Dict[str, Any]:
        """Provides an intelligent classification of the current market volatility."""
        required_cols = [self.atr_col, self.atr_pct_col]
        valid_df = self.df.dropna(subset=required_cols)
        
        if len(valid_df) < 1:
            return {"status": "Insufficient Data", "timeframe": self.timeframe or 'Base'}
        
        last_atr_val = valid_df[self.atr_col].iloc[-1]
        last_atr_pct = valid_df[self.atr_pct_col].iloc[-1]
        
        # --- Volatility Level Analysis ---
        t = self.volatility_thresholds
        if last_atr_pct <= t['low_max']: volatility_level = "Low"
        elif last_atr_pct <= t['normal_max']: volatility_level = "Normal"
        elif last_atr_pct <= t['high_max']: volatility_level = "High"
        else: volatility_level = "Extreme"

        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "values": {
                "atr": round(last_atr_val, 5),
                "atr_percent": round(last_atr_pct, 2),
            },
            "analysis": {
                "volatility": volatility_level
            }
        }
