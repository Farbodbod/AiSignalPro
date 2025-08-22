# backend/engines/indicators/williams_r.py (v6.0 - The Dynamic Engine)
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Optional

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class WilliamsRIndicator(BaseIndicator):
    """
    Williams %R - (v6.0 - The Dynamic Engine)
    -------------------------------------------------------------------------
    This world-class version is fully standardized and hardened. It features
    a dynamic, multi-instance-safe architecture, a robust ffill/bfill data
    integrity shield, and a fully Sentinel-compliant output structure, making
    it a flawless component for the AiSignalPro ecosystem.
    """
    dependencies: list = []

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.period = int(self.params.get('period', 14))
        self.overbought = float(self.params.get('overbought', -20.0))
        self.oversold = float(self.params.get('oversold', -80.0))
        self.timeframe = self.params.get('timeframe')
        
        # ✅ DYNAMIC ARCHITECTURE: Column name is now based on parameters.
        suffix = f'_{self.period}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        else: suffix += '_base'
        self.wr_col = f'wr{suffix}'

    def calculate(self) -> 'WilliamsRIndicator':
        if len(self.df) < self.period:
            logger.warning(f"Not enough data for Williams %R on {self.timeframe or 'base'}.")
            self.df[self.wr_col] = np.nan
            return self

        highest_high = self.df['high'].rolling(window=self.period).max()
        lowest_low = self.df['low'].rolling(window=self.period).min()
        
        denominator = (highest_high - lowest_low).replace(0, np.nan)
        numerator = highest_high - self.df['close']
        
        wr_series = (numerator / denominator) * -100
        
        # ✅ HARDENED FILL (v6.0): Use the standard ffill/bfill logic for robustness.
        self.df[self.wr_col] = wr_series.ffill(limit=3).bfill(limit=2)
        return self

    def analyze(self) -> Dict[str, Any]:
        empty_analysis = {"values": {}, "analysis": {}}
        if self.wr_col not in self.df.columns or self.df[self.wr_col].isnull().all():
            return {"status": "Calculation Incomplete", **empty_analysis}

        valid_df = self.df.dropna(subset=[self.wr_col])
        if len(valid_df) < 2: 
            return {"status": "Insufficient Data", **empty_analysis}

        last = valid_df.iloc[-1]
        prev = valid_df.iloc[-2]
        last_wr = last[self.wr_col]
        prev_wr = prev[self.wr_col]

        position = "Neutral"
        if last_wr >= self.overbought: position = "Overbought"
        elif last_wr <= self.oversold: position = "Oversold"
            
        signal = "Hold"
        if prev_wr <= self.oversold and last_wr > self.oversold: signal = "Oversold Exit (Buy)"
        elif prev_wr >= self.overbought and last_wr < self.overbought: signal = "Overbought Exit (Sell)"

        slope = last_wr - prev_wr
        momentum = "Rising" if slope > 0 else "Falling" if slope < 0 else "Flat"
        
        values_content = {"wr": round(last_wr, 2)}
        analysis_content = {
            "position": position,
            "crossover_signal": signal,
            "momentum": {"direction": momentum, "slope": round(slope, 2)},
            "divergences": []
        }
        
        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "values": values_content,
            "analysis": analysis_content
        }
