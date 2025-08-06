import pandas as pd
import pandas_ta as ta
import logging
import warnings
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class PatternIndicator(BaseIndicator):
    """
    ✨ UPGRADE v2.0 ✨
    - Constructor standardized to use **kwargs.
    - Ensures compatibility with the project's standard structure.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.pattern_col = 'identified_pattern'

    def calculate(self) -> pd.DataFrame:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                patterns_df = self.df.ta.cdl_pattern(name="all")
            
            # Use a more robust way to assign patterns
            self.df[self.pattern_col] = "None"
            if patterns_df is not None and not patterns_df.empty:
                # Find all patterns for the last candle
                last_candle_patterns = patterns_df.iloc[-1]
                found_patterns = last_candle_patterns[last_candle_patterns != 0]
                if not found_patterns.empty:
                    pattern_names = [col.replace('CDL_', '') for col in found_patterns.index]
                    self.df.loc[self.df.index[-1], self.pattern_col] = ", ".join(pattern_names)
        except Exception as e:
            logger.error(f"Error calculating candlestick patterns: {e}")
            self.df[self.pattern_col] = "Error"
        return self.df

    def analyze(self) -> dict:
        last_patterns_str = self.df.iloc[-1].get(self.pattern_col, "None")
        if last_patterns_str in ["None", "Error"] or pd.isna(last_patterns_str):
            return {"patterns": []}
        return {"patterns": [p.strip() for p in last_patterns_str.split(',')]}
