import pandas as pd
import numpy as np
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class AtrIndicator(BaseIndicator):
    """
    ATR Indicator - World-Class, Intelligent & Robust Version
    ----------------------------------------------------------
    This version includes:
    1.  Accurate Wilder's Smoothing for ATR calculation.
    2.  An additional 'Normalized ATR' column (% of close price).
    3.  Robust input validation and error handling.
    4.  Intelligent analysis classifying volatility into levels (Low, Normal, High).
    5.  Parameterizable thresholds for volatility analysis.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        # --- Parameterization ---
        self.period = int(self.params.get('period', 14))
        # ✨ IMPROVEMENT 1: Make volatility analysis thresholds configurable
        self.volatility_thresholds = self.params.get('volatility_thresholds', {
            'low_max': 1.0,   # ATR percent below this is "Low"
            'normal_max': 3.0, # ATR percent below this is "Normal"
            'high_max': 5.0    # ATR percent below this is "High", above is "Extreme"
        })
        
        # --- Column Naming ---
        self.atr_col = f'atr_{self.period}'
        self.atr_pct_col = f'atr_pct_{self.period}'

    def _validate_input(self, df: pd.DataFrame) -> pd.DataFrame:
        """Validates the input DataFrame for required columns, length, and dtype."""
        required_cols = {'high', 'low', 'close'}
        if not required_cols.issubset(df.columns):
            missing = required_cols - set(df.columns)
            msg = f"Missing required columns for ATR: {missing}"
            logger.error(msg)
            raise ValueError(msg)
        
        if len(df) < self.period:
            logger.warning(f"Data length ({len(df)}) is less than ATR period ({self.period}). Results might be unreliable.")
        
        for col in required_cols:
            if not pd.api.types.is_numeric_dtype(df[col]):
                df[col] = pd.to_numeric(df[col], errors='coerce')
        return df

    def calculate(self) -> pd.DataFrame:
        """Calculates ATR and Normalized ATR, adding them to the DataFrame."""
        df = self.df.copy()
        df = self._validate_input(df)

        # True Range (TR) calculation
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift(1))
        low_close = np.abs(df['low'] - df['close'].shift(1))
        
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        
        # Use Wilder's Smoothing (RMA) for ATR
        atr = tr.ewm(alpha=1/self.period, adjust=False).mean()
        self.df[self.atr_col] = atr

        # Normalized ATR (% of close price) calculation
        # Using np.where for safe division, propagating NaN if close is 0 or NaN
        safe_close = df['close'].replace(0, np.nan)
        self.df[self.atr_pct_col] = (atr / safe_close) * 100
        
        return self.df

    def analyze(self) -> dict:
        """
        Analyzes the latest ATR value and provides an intelligent classification
        of the current market volatility.
        """
        # ✨ IMPROVEMENT 2: Robust check for data availability and NaN values
        if len(self.df) < 1 or pd.isna(self.df[self.atr_pct_col].iloc[-1]):
            return {"value": None, "percent": None, "volatility": "Insufficient Data"}

        last_atr_val = self.df[self.atr_col].iloc[-1]
        last_atr_pct = self.df[self.atr_pct_col].iloc[-1]

        # --- Volatility Level Analysis (using configurable thresholds) ---
        t = self.volatility_thresholds
        if last_atr_pct <= t['low_max']:
            volatility_level = "Low"
        elif last_atr_pct <= t['normal_max']:
            volatility_level = "Normal"
        elif last_atr_pct <= t['high_max']:
            volatility_level = "High"
        else:
            volatility_level = "Extreme"

        return {
            "value": round(last_atr_val, 5),
            "percent": round(last_atr_pct, 2),
            "volatility": volatility_level
        }
