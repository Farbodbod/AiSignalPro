# backend/engines/indicators/obv.py (v5.0 - The Quantum Flow Edition)
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class ObvIndicator(BaseIndicator):
    """
    On-Balance Volume (OBV) - (v5.0 - The Quantum Flow Edition)
    ------------------------------------------------------------------------------------
    This world-class version evolves OBV into a quantum flow engine. It introduces
    a 0-100 signal strength score, Rate of Change (ROC) for momentum analysis, and
    expressive summaries. The architecture is fully hardened with dynamic column
    naming, data filling, and a Sentinel-compliant output.
    """
    dependencies: list = []

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.signal_period = int(self.params.get('signal_period', 20))
        self.rvol_period = int(self.params.get('rvol_period', 20))
        self.price_ma_period = int(self.params.get('price_ma_period', 20))
        self.rvol_threshold = float(self.params.get('rvol_threshold', 1.5))
        self.roc_period = int(self.params.get('roc_period', 5))
        self.timeframe = self.params.get('timeframe', None)

        # ✅ FINAL STANDARD: Dynamic and conflict-proof column naming.
        suffix = f'_{self.signal_period}_{self.rvol_period}_{self.price_ma_period}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        else: suffix += '_base'
        
        self.obv_col = f'obv{suffix}'
        self.obv_signal_col = f'obv_signal{suffix}'
        self.rvol_col = f'rvol{suffix}'
        self.price_ma_col = f'price_ma{suffix}'
        self.obv_roc_col = f'obv_roc{suffix}'

    def calculate(self) -> 'ObvIndicator':
        if len(self.df) < max(self.signal_period, self.rvol_period, self.price_ma_period):
            logger.warning(f"Not enough data for OBV on {self.timeframe or 'base'}.")
            for col in [self.obv_col, self.obv_signal_col, self.rvol_col, self.price_ma_col, self.obv_roc_col]:
                self.df[col] = np.nan
            return self

        obv_raw = np.where(self.df['close'] > self.df['close'].shift(1), self.df['volume'],
                  np.where(self.df['close'] < self.df['close'].shift(1), -self.df['volume'], 0)).cumsum()
        
        obv_series = pd.Series(obv_raw, index=self.df.index)
        obv_signal_series = obv_series.ewm(span=self.signal_period, adjust=False).mean()
        
        vol_ma = self.df['volume'].rolling(window=self.rvol_period).mean().replace(0, np.nan)
        rvol_series = self.df['volume'] / vol_ma
        rvol_series.replace([np.inf, -np.inf], np.nan, inplace=True)
        
        price_ma_series = self.df['close'].ewm(span=self.price_ma_period, adjust=False).mean()
        
        obv_roc_series = obv_series.pct_change(periods=self.roc_period) * 100
        
        # ✅ HARDENED FILL: Add a limited ffill/bfill for robustness.
        fill_limit = 3
        self.df[self.obv_col] = obv_series.ffill(limit=fill_limit).bfill(limit=2)
        self.df[self.obv_signal_col] = obv_signal_series.ffill(limit=fill_limit).bfill(limit=2)
        self.df[self.rvol_col] = rvol_series.ffill(limit=fill_limit).bfill(limit=2)
        self.df[self.price_ma_col] = price_ma_series.ffill(limit=fill_limit).bfill(limit=2)
        self.df[self.obv_roc_col] = obv_roc_series.ffill(limit=fill_limit).bfill(limit=2)

        return self

    def analyze(self) -> Dict[str, Any]:
        required_cols = [self.obv_col, self.obv_signal_col, self.rvol_col, self.price_ma_col, 'close']
        empty_analysis = {"values": {}, "analysis": {}}
        if not all(col in self.df.columns for col in required_cols):
            return {"status": "Calculation Incomplete", **empty_analysis}

        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 2:
            return {"status": "Insufficient Data", **empty_analysis}

        last, prev = valid_df.iloc[-1], valid_df.iloc[-2]

        primary_event = "Neutral"
        if prev[self.obv_col] <= prev[self.obv_signal_col] and last[self.obv_col] > last[self.obv_signal_col]:
            primary_event = "Bullish Crossover"
        elif prev[self.obv_col] >= prev[self.obv_signal_col] and last[self.obv_col] < last[self.obv_signal_col]:
            primary_event = "Bearish Crossover"
            
        volume_confirmed = last[self.rvol_col] > self.rvol_threshold
        price_confirmed = False
        if "Bullish" in primary_event: price_confirmed = last['close'] > last[self.price_ma_col]
        elif "Bearish" in primary_event: price_confirmed = last['close'] < last[self.price_ma_col]
            
        # ✅ QUANTUM SCORE & EXPRESSIVE SUMMARY
        strength_score = 0; final_signal = "Hold"; summary = "Neutral volume flow."
        if primary_event != "Neutral":
            strength_score += 40 # Base score for crossover
            if volume_confirmed: strength_score += 30
            if price_confirmed: strength_score += 30
            
            direction = primary_event.split(' ')[0]
            if strength_score >= 70: final_signal = f"Strong {direction}"
            elif strength_score >= 40: final_signal = f"Weak {direction}"

            summary = f"{final_signal} signal detected ({primary_event}) "
            summary += "confirmed by High Volume and Price Action." if volume_confirmed and price_confirmed else \
                       "confirmed by High Volume." if volume_confirmed else \
                       "confirmed by Price Action." if price_confirmed else \
                       "with no extra confirmation."
        
        values_content = {
            "obv": int(last[self.obv_col]), "obv_signal_line": int(last[self.obv_signal_col]),
            "rvol": round(last[self.rvol_col], 2), "price_ma": round(last[self.price_ma_col], 5),
            "obv_roc_percent": round(last.get(self.obv_roc_col, 0), 2)
        }
        analysis_content = {
            "signal": final_signal, "strength_score": strength_score,
            "primary_event": primary_event,
            "confirmation": {"volume_confirmed": volume_confirmed, "price_confirmed": price_confirmed},
            "summary": summary
        }
        
        return {
            "status": "OK", "timeframe": self.timeframe or 'Base',
            "values": values_content, "analysis": analysis_content
        }
