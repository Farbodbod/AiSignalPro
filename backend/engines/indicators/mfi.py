# backend/engines/indicators/mfi.py (v5.0 - The Quantum Flow Edition)
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class MfiIndicator(BaseIndicator):
    """
    Money Flow Index (MFI) - (v5.0 - The Quantum Flow Edition)
    -------------------------------------------------------------------------------------
    This world-class version evolves into a quantum flow engine. It introduces a
    0-100 strength score, volume context analysis, and expressive summaries. The
    architecture is fully standardized with dynamic column naming, hardened data
    filling, and a Sentinel-compliant output for flawless integration.
    """
    dependencies: list = []

    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], **kwargs):
        super().__init__(df, params=params, **kwargs)
        self.period = int(self.params.get('period', 14))
        self.timeframe = self.params.get('timeframe')
        # Granular thresholds
        self.overbought = float(self.params.get('overbought', 80.0))
        self.oversold = float(self.params.get('oversold', 20.0))
        self.extreme_overbought = float(self.params.get('extreme_overbought', 90.0))
        self.extreme_oversold = float(self.params.get('extreme_oversold', 10.0))
        
        # ✅ FINAL STANDARD: Dynamic and conflict-proof column naming.
        suffix = f'_{self.period}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        else: suffix += '_base'
        self.mfi_col = f'mfi{suffix}'
        self.vol_ma_col = f'mfi_vol_ma{suffix}' # For context analysis

    def calculate(self) -> 'MfiIndicator':
        if len(self.df) < self.period:
            logger.warning(f"Not enough data for MFI on {self.timeframe or 'base'}.")
            self.df[self.mfi_col] = np.nan
            return self

        tp = (self.df['high'] + self.df['low'] + self.df['close']) / 3
        raw_money_flow = tp * self.df['volume']
        price_diff = tp.diff(1)
        
        pos_flow = np.where(price_diff > 0, raw_money_flow, 0)
        neg_flow = np.where(price_diff < 0, raw_money_flow, 0)

        pos_mf_sum = pd.Series(pos_flow, index=self.df.index).rolling(window=self.period).sum()
        neg_mf_sum = pd.Series(neg_flow, index=self.df.index).rolling(window=self.period).sum()

        money_ratio = pos_mf_sum / neg_mf_sum.replace(0, np.nan)
        mfi = 100 - (100 / (1 + money_ratio))
        
        # ✅ HARDENED FILL: Use the standard ffill/bfill logic for robustness.
        self.df[self.mfi_col] = mfi.ffill(limit=3).bfill(limit=2)
        
        # Calculate volume context for analysis phase
        self.df[self.vol_ma_col] = self.df['volume'].rolling(window=self.period).mean()
        return self
    
    def analyze(self) -> Dict[str, Any]:
        required_cols = [self.mfi_col, 'volume', self.vol_ma_col]
        empty_analysis = {"values": {}, "analysis": {}}
        if not all(col in self.df.columns for col in required_cols):
            return {"status": "Calculation Incomplete", **empty_analysis}

        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 2: 
            return {"status": "Insufficient Data", **empty_analysis}
        
        last = valid_df.iloc[-1]; prev = valid_df.iloc[-2]
        last_mfi, prev_mfi = last[self.mfi_col], prev[self.mfi_col]

        position = "Neutral"
        if last_mfi >= self.extreme_overbought: position = "Extreme Overbought"
        elif last_mfi >= self.overbought: position = "Overbought"
        elif last_mfi <= self.extreme_oversold: position = "Extreme Oversold"
        elif last_mfi <= self.oversold: position = "Oversold"

        signal = "Hold"
        if prev_mfi <= self.oversold and last_mfi > self.oversold: signal = "Oversold Exit (Buy)"
        elif prev_mfi >= self.overbought and last_mfi < self.overbought: signal = "Overbought Exit (Sell)"
        elif prev_mfi <= 50 and last_mfi > 50: signal = "Bullish Centerline Cross"
        elif prev_mfi >= 50 and last_mfi < 50: signal = "Bearish Centerline Cross"
            
        # ✅ QUANTUM FEATURES: Strength Score & Volume Context
        strength = int(abs(last_mfi - 50) * 2)
        volume_context = "High Volume" if last["volume"] > last[self.vol_ma_col] * 1.5 else "Normal Volume"
        
        # ✅ EXPRESSIVE SUMMARY
        summary = f"Position: {position} | Signal: {signal}"
        if "Extreme" in position:
            summary = f"{'Bearish' if 'Overbought' in position else 'Bullish'} Warning: {position} with {volume_context}"
        elif "Cross" in signal:
            summary = f"Potential {'Bullish' if 'Bullish' in signal else 'Bearish'} signal: {signal} on {volume_context}"

        values_content = {"mfi": round(last_mfi, 2), "strength": strength}
        analysis_content = {
            "position": position, "crossover_signal": signal,
            "strength": strength, "volume_context": volume_context,
            "summary": summary, "divergences": []
        }

        return {
            "status": "OK", "timeframe": self.timeframe or 'Base',
            "values": values_content, "analysis": analysis_content
        }
