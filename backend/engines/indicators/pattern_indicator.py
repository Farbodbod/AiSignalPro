import pandas as pd
import numpy as np
import logging
import warnings
from typing import Dict, Any, List

try:
    import pandas_ta as ta
except ImportError:
    ta = None

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class PatternIndicator(BaseIndicator):
    """
    Candlestick Pattern Engine - Definitive, World-Class Version (v3.0 - Final Architecture)
    ---------------------------------------------------------------------------------------
    This version acts as an intelligent interpretation layer on top of pandas_ta.
    It adheres to the final AiSignalPro architecture by calculating on the
    pre-resampled dataframe.
    """
    dependencies: list = []
    
    PATTERN_INFO = {
        'CDL_HAMMER': {'name': 'Hammer', 'type': 'Bullish', 'reliability': 'Medium'},
        'CDL_INVERTEDHAMMER': {'name': 'Inverted Hammer', 'type': 'Bullish', 'reliability': 'Medium'},
        'CDL_BULLISHENGULFING': {'name': 'Bullish Engulfing', 'type': 'Bullish', 'reliability': 'Strong'},
        'CDL_PIERCING': {'name': 'Piercing Line', 'type': 'Bullish', 'reliability': 'Strong'},
        'CDL_MORNINGSTAR': {'name': 'Morning Star', 'type': 'Bullish', 'reliability': 'Strong'},
        'CDL_3WHITESOLDIERS': {'name': 'Three White Soldiers', 'type': 'Bullish', 'reliability': 'Strong'},
        'CDL_HARAMI': {'name': 'Harami', 'type': 'Bi-Directional', 'reliability': 'Medium'},
        'CDL_3INSIDE': {'name': 'Three Inside Up/Down', 'type': 'Bi-Directional', 'reliability': 'Strong'},
        'CDL_HANGINGMAN': {'name': 'Hanging Man', 'type': 'Bearish', 'reliability': 'Medium'},
        'CDL_SHOOTINGSTAR': {'name': 'Shooting Star', 'type': 'Bearish', 'reliability': 'Medium'},
        'CDL_BEARISHENGULFING': {'name': 'Bearish Engulfing', 'type': 'Bearish', 'reliability': 'Strong'},
        'CDL_DARKCLOUDCOVER': {'name': 'Dark Cloud Cover', 'type': 'Bearish', 'reliability': 'Strong'},
        'CDL_EVENINGSTAR': {'name': 'Evening Star', 'type': 'Bearish', 'reliability': 'Strong'},
        'CDL_3BLACKCROWS': {'name': 'Three Black Crows', 'type': 'Bearish', 'reliability': 'Strong'},
        'CDL_DOJI': {'name': 'Doji', 'type': 'Neutral', 'reliability': 'Low'},
        'CDL_SPINNINGTOP': {'name': 'Spinning Top', 'type': 'Neutral', 'reliability': 'Low'},
        'CDL_MARUBOZU': {'name': 'Marubozu', 'type': 'Bi-Directional', 'reliability': 'Strong'},
        'CDL_RISEFALL3METHODS': {'name': 'Rising/Falling Three Methods', 'type': 'Bi-Directional', 'reliability': 'Strong'},
    }

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        if ta is None:
            raise ImportError("pandas_ta is not installed. Please install it using 'pip install pandas_ta'")
        self.params = kwargs.get('params', {})
        self.timeframe = self.params.get('timeframe', None)
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
                    pattern_details['score'] = int(score)
                    if pattern_details['type'] == 'Bi-Directional':
                        pattern_details['type'] = 'Bullish' if score > 0 else 'Bearish'
                    if col == 'CDL_HARAMI':
                        pattern_details['name'] = 'Bullish Harami' if score > 0 else 'Bearish Harami'
                    if col == 'CDL_3INSIDE':
                        pattern_details['name'] = 'Three Inside Up' if score > 0 else 'Three Inside Down'
                    found_patterns.append(pattern_details)
            return found_patterns

        res[self.patterns_col] = patterns_df.apply(process_row, axis=1)
        return res

    def calculate(self) -> 'PatternIndicator':
        """
        ✨ FINAL ARCHITECTURE: No resampling. Just pure calculation.
        The dataframe received is already at the correct timeframe.
        """
        df_for_calc = self.df
        
        if len(df_for_calc) == 0:
            logger.warning(f"Not enough data for Pattern Recognition on timeframe {self.timeframe or 'base'}.")
            self.df[self.patterns_col] = [[] for _ in range(len(self.df))]
            return self

        pattern_results = self._calculate_patterns(df_for_calc)
        
        self.df[self.patterns_col] = pattern_results[self.patterns_col]
        self.df[self.patterns_col] = self.df[self.patterns_col].apply(lambda x: x if isinstance(x, list) else [])
        
        return self

    def analyze(self) -> Dict[str, Any]:
        """
        Provides a bias-free analysis of the patterns found on the last closed candle.
        This powerful analysis logic remains unchanged.
        """
        if self.patterns_col not in self.df.columns or len(self.df) < 2:
            return {"status": "No Data", "analysis": {}}
        
        last_closed_patterns = self.df[self.patterns_col].iloc[-2]
        if not isinstance(last_closed_patterns, list): last_closed_patterns = []
            
        bullish_patterns = [p for p in last_closed_patterns if p.get('type') == 'Bullish']
        bearish_patterns = [p for p in last_closed_patterns if p.get('type') == 'Bearish']
        
        signal = "Neutral"
        if bullish_patterns and not bearish_patterns: signal = "Bullish"
        elif bearish_patterns and not bullish_patterns: signal = "Bearish"
            
        return {
            "status": "OK", "timeframe": self.timeframe or 'Base',
            "analysis": {
                "signal": signal,
                "bullish_patterns": bullish_patterns,
                "bearish_patterns": bearish_patterns,
                "neutral_patterns": [p for p in last_closed_patterns if p.get('type') == 'Neutral'],
                "pattern_count": len(last_closed_patterns)
            }
        }
