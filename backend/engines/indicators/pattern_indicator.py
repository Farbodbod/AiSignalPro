import pandas as pd
import numpy as np
import logging
import warnings
from typing import Dict, Any, List
# فرض بر این است که pandas_ta نصب شده است
try:
    import pandas_ta as ta
except ImportError:
    ta = None

# اطمینان حاصل کنید که این اندیکاتور از فایل مربوطه وارد شده‌ است
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class PatternIndicator(BaseIndicator):
    """
    Candlestick Pattern Engine - Definitive, MTF & World-Class Version 2.0
    -------------------------------------------------------------------------
    This version expands the pattern recognition library to include key
    continuation and confirmed reversal patterns, making it a comprehensive
    tool for automated trading systems.
    """
    # ✨ The core intelligence: Expanded with strategic patterns
    PATTERN_INFO = {
        # --- Bullish Reversal Patterns ---
        'CDL_HAMMER': {'name': 'Hammer', 'type': 'Bullish', 'reliability': 'Medium'},
        'CDL_INVERTEDHAMMER': {'name': 'Inverted Hammer', 'type': 'Bullish', 'reliability': 'Medium'},
        'CDL_BULLISHENGULFING': {'name': 'Bullish Engulfing', 'type': 'Bullish', 'reliability': 'Strong'},
        'CDL_PIERCING': {'name': 'Piercing Line', 'type': 'Bullish', 'reliability': 'Strong'},
        'CDL_MORNINGSTAR': {'name': 'Morning Star', 'type': 'Bullish', 'reliability': 'Strong'},
        'CDL_3WHITESOLDIERS': {'name': 'Three White Soldiers', 'type': 'Bullish', 'reliability': 'Strong'},
        'CDL_HARAMI': {'name': 'Harami', 'type': 'Bullish', 'reliability': 'Medium'}, # Note: pandas_ta signals bullish Harami with +100
        'CDL_3INSIDE': {'name': 'Three Inside Up', 'type': 'Bullish', 'reliability': 'Strong'}, # Note: pandas_ta signals bullish version with +100

        # --- Bearish Reversal Patterns ---
        'CDL_HANGINGMAN': {'name': 'Hanging Man', 'type': 'Bearish', 'reliability': 'Medium'},
        'CDL_SHOOTINGSTAR': {'name': 'Shooting Star', 'type': 'Bearish', 'reliability': 'Medium'},
        'CDL_BEARISHENGULFING': {'name': 'Bearish Engulfing', 'type': 'Bearish', 'reliability': 'Strong'},
        'CDL_DARKCLOUDCOVER': {'name': 'Dark Cloud Cover', 'type': 'Bearish', 'reliability': 'Strong'},
        'CDL_EVENINGSTAR': {'name': 'Evening Star', 'type': 'Bearish', 'reliability': 'Strong'},
        'CDL_3BLACKCROWS': {'name': 'Three Black Crows', 'type': 'Bearish', 'reliability': 'Strong'},
        # Note: Bearish Harami and Three Inside Down are detected by the same functions with a -100 score.

        # --- Indecision / Neutral Patterns ---
        'CDL_DOJI': {'name': 'Doji', 'type': 'Neutral', 'reliability': 'Low'},
        'CDL_SPINNINGTOP': {'name': 'Spinning Top', 'type': 'Neutral', 'reliability': 'Low'},

        # ✨ --- STRATEGIC ADDITIONS ---
        # Note: These patterns are bi-directional. The 'type' is determined by the score (+100 Bullish, -100 Bearish).
        'CDL_MARUBOZU': {'name': 'Marubozu', 'type': 'Bi-Directional', 'reliability': 'Strong'},
        'CDL_RISEFALL3METHODS': {'name': 'Rising/Falling Three Methods', 'type': 'Bi-Directional', 'reliability': 'Strong'},
    }

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        if ta is None:
            raise ImportError("pandas_ta is not installed. Please install it using 'pip install pandas_ta'")
        
        self.params = kwargs.get('params', {})
        self.timeframe = self.params.get('timeframe', None)

        # --- Dynamic Column Naming ---
        suffix = f'_{self.timeframe}' if self.timeframe else ''
        self.patterns_col = f'patterns{suffix}'

    def _calculate_patterns(self, df: pd.DataFrame) -> pd.DataFrame:
        """The core logic to run pandas_ta and interpret its results."""
        res = pd.DataFrame(index=df.index)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            patterns_df = df.ta.cdl_pattern(name="all")
        
        if patterns_df is None or patterns_df.empty:
            res[self.patterns_col] = [[] for _ in range(len(df))]; return res

        known_pattern_cols = [col for col in self.PATTERN_INFO.keys() if col in patterns_df.columns]
        
        def process_row(row):
            found_patterns = []
            for col in known_pattern_cols:
                if row[col] != 0:
                    pattern_details = self.PATTERN_INFO[col].copy()
                    score = row[col]
                    pattern_details['score'] = score
                    # For bi-directional patterns, set the type based on the score
                    if pattern_details['type'] == 'Bi-Directional':
                        pattern_details['type'] = 'Bullish' if score > 0 else 'Bearish'
                    # For Harami, override name based on direction
                    if col == 'CDL_HARAMI':
                        pattern_details['name'] = 'Bullish Harami' if score > 0 else 'Bearish Harami'
                    if col == 'CDL_3INSIDE':
                        pattern_details['name'] = 'Three Inside Up' if score > 0 else 'Three Inside Down'
                    found_patterns.append(pattern_details)
            return found_patterns

        res[self.patterns_col] = patterns_df.apply(process_row, axis=1)
        return res

    def calculate(self) -> 'PatternIndicator':
        # ... (The MTF calculate logic remains unchanged, it's already perfect) ...
        base_df = self.df
        if self.timeframe:
            if not isinstance(base_df.index, pd.DatetimeIndex): raise TypeError("DatetimeIndex required for MTF.")
            rules = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume':'sum'}
            calc_df = base_df.resample(self.timeframe, label='right', closed='right').apply(rules).dropna()
        else:
            calc_df = base_df.copy()
        if len(calc_df) == 0: logger.warning(f"No data for timeframe {self.timeframe or 'base'}."); return self
        pattern_results = self._calculate_patterns(calc_df)
        if self.timeframe: self.df[self.patterns_col] = pattern_results.reindex(base_df.index, method='ffill')
        else: self.df[self.patterns_col] = pattern_results[self.patterns_col]
        self.df[self.patterns_col] = self.df[self.patterns_col].apply(lambda x: x if isinstance(x, list) else [])
        return self

    def analyze(self) -> Dict[str, Any]:
        # ... (The bias-free analyze logic remains unchanged, it's already perfect) ...
        if self.patterns_col not in self.df.columns or len(self.df) < 2: return {"status": "No Data", "analysis": {}}
        last_closed_patterns = self.df[self.patterns_col].iloc[-2]
        bullish_patterns = [p for p in last_closed_patterns if p.get('type') == 'Bullish']
        bearish_patterns = [p for p in last_closed_patterns if p.get('type') == 'Bearish']
        signal = "Neutral"
        if bullish_patterns and not bearish_patterns: signal = "Bullish"
        elif bearish_patterns and not bullish_patterns: signal = "Bearish"
        return {
            "status": "OK", "timeframe": self.timeframe or 'Base',
            "analysis": { "signal": signal, "bullish_patterns": bullish_patterns, "bearish_patterns": bearish_patterns,
                          "neutral_patterns": [p for p in last_closed_patterns if p.get('type') == 'Neutral'],
                          "pattern_count": len(last_closed_patterns)
            }
        }
