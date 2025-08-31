# backend/engines/indicators/volume.py (v2.0 - The Volume Quantum Engine)
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class VolumeIndicator(BaseIndicator):
    """
    Volume Indicator - (v2.0 - The Volume Quantum Engine)
    ---------------------------------------------------------------------------
    This quantum upgrade transforms the volume indicator into a multi-dimensional
    analysis engine, fully aligned with the AiSignalPro's "smart module"
    architecture.

    Key Features:
    1.  **Standardized Architecture:** Now uses the project's gold-standard
        'default_config' pattern for maximum clarity and maintainability.
    2.  **Z-Score Analysis:** Integrates standard Z-Score calculation, providing
        a statistically robust measure of volume intensity for advanced strategies.
    3.  **Dynamic Volume Regime Intelligence:** Implements percentile-based analysis
        to classify the market's volume state into 'Squeeze', 'Normal', or
        'Expansion', offering deep, predictive context.
    4.  **Full Compatibility:** Includes a 'series' output for full integration
        with momentum acceleration logic in consuming strategies.
    """
    dependencies: list = []
    
    default_config: Dict[str, Any] = {
        'period': 20,
        'long_period': 50,
        'climactic_std_threshold': 2.5,
        'regime_period': 200,
        'squeeze_percentile': 20,
        'expansion_percentile': 80,
        'series_lookback': 5,
    }

    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], **kwargs):
        super().__init__(df, params=params, **kwargs)
        self.period = int(self.params.get('period', self.default_config['period']))
        self.long_period = int(self.params.get('long_period', self.default_config['long_period']))
        self.climactic_std_threshold = float(self.params.get('climactic_std_threshold', self.default_config['climactic_std_threshold']))
        self.regime_period = int(self.params.get('regime_period', self.default_config['regime_period']))
        self.squeeze_percentile = int(self.params.get('squeeze_percentile', self.default_config['squeeze_percentile']))
        self.expansion_percentile = int(self.params.get('expansion_percentile', self.default_config['expansion_percentile']))
        self.series_lookback = int(self.params.get('series_lookback', self.default_config['series_lookback']))
        self.timeframe = self.params.get('timeframe')
        
        suffix = f'_{self.period}_{self.long_period}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        
        self.volume_ma_col = f'vol_ma{suffix}'
        self.volume_ma_long_col = f'vol_ma_long{suffix}'
        self.volume_std_col = f'vol_std{suffix}'
        self.z_score_col = f'vol_zscore{suffix}'
        self.volume_percentile_col = f'vol_pct{suffix}'

    def calculate(self) -> 'VolumeIndicator':
        if 'volume' not in self.df.columns or len(self.df) < self.long_period or len(self.df) < self.regime_period:
            logger.warning(f"Not enough data or missing 'volume' column for VolumeIndicator on timeframe {self.timeframe or 'base'}.")
            return self

        volume = self.df['volume']
        
        # Standard Calculations
        volume_ma = volume.rolling(window=self.period).mean()
        volume_ma_long = volume.rolling(window=self.long_period).mean()
        volume_std = volume.rolling(window=self.period).std().replace(0, 1e-9) # Avoid division by zero
        
        # ✅ QUANTUM ANALYSIS: Z-Score Calculation
        z_score = (volume - volume_ma) / volume_std
        
        # ✅ DYNAMIC REGIME: Volume Percentile Calculation
        volume_percentile = volume.rolling(window=self.regime_period, min_periods=int(self.regime_period/2)).rank(pct=True) * 100
        
        # Assign to DataFrame
        self.df[self.volume_ma_col] = volume_ma
        self.df[self.volume_ma_long_col] = volume_ma_long
        self.df[self.volume_std_col] = volume_std
        self.df[self.z_score_col] = z_score
        self.df[self.volume_percentile_col] = volume_percentile
            
        return self

    def analyze(self) -> Dict[str, Any]:
        required_cols = [self.volume_ma_col, self.volume_ma_long_col, self.z_score_col, self.volume_percentile_col]
        empty_analysis = {"values": {}, "analysis": {}, "series": []}

        if any(col not in self.df.columns for col in required_cols) or self.df['volume'].isnull().all():
            return {"status": "Calculation Incomplete", **empty_analysis}

        valid_df = self.df.dropna(subset=required_cols + ['volume'])
        if valid_df.empty:
            return {"status": "Insufficient Data", **empty_analysis}
        
        last = valid_df.iloc[-1]
        
        # --- 1. Basic Analysis ---
        volume_trend = "Increasing" if last[self.volume_ma_col] > last[self.volume_ma_long_col] else "Decreasing" if last[self.volume_ma_col] < last[self.volume_ma_long_col] else "Neutral"
        
        # --- 2. Z-Score Based Climactic Check ---
        z_score = last[self.z_score_col]
        is_climactic = z_score > self.climactic_std_threshold
        
        # --- 3. Dynamic Volume Regime Analysis ---
        volume_percentile = last[self.volume_percentile_col]
        volume_regime = "Normal"
        if volume_percentile <= self.squeeze_percentile:
            volume_regime = "Squeeze"
        elif volume_percentile >= self.expansion_percentile:
            volume_regime = "Expansion"

        # --- 4. Assemble Final Output ---
        values_content = {
            "volume": float(last['volume']),
            "volume_ma": float(last[self.volume_ma_col]),
            "z_score": round(z_score, 2),
            "volume_percentile": round(volume_percentile, 2)
        }

        analysis_content = {
            "is_above_average": bool(last['volume'] > last[self.volume_ma_col]),
            "is_climactic_volume": bool(is_climactic),
            "volume_trend": volume_trend,
            "volume_regime": volume_regime,
        }
        
        series_content = [float(v) for v in self.df['volume'].tail(self.series_lookback).tolist()]

        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "values": values_content,
            "analysis": analysis_content,
            "series": series_content
        }
