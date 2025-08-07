import pandas as pd
import logging
import warnings
from candlestick import (
    cdl_engulfing, cdl_morning_star, cdl_evening_star, cdl_hammer,
    cdl_shooting_star, cdl_bullish_harami, cdl_bearish_harami,
    cdl_doji, cdl_piercing_pattern, cdl_dark_cloud_cover,
    cdl_three_white_soldiers, cdl_three_black_crows,
    cdl_inverted_hammer, cdl_marubozu, cdl_inside_bar,
    cdl_outside_bar, cdl_spinning_top
)
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class PatternIndicator(BaseIndicator):
    """
    ⚡ PatternIndicator (candlestick v0.1.8 compatible)
    - Detects 18 advanced candlestick patterns
    - Designed for AI Signal Pro infrastructure
    """

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.pattern_col = 'identified_pattern'
        self.pattern_functions = [
            cdl_engulfing, cdl_morning_star, cdl_evening_star, cdl_hammer,
            cdl_shooting_star, cdl_bullish_harami, cdl_bearish_harami,
            cdl_doji, cdl_piercing_pattern, cdl_dark_cloud_cover,
            cdl_three_white_soldiers, cdl_three_black_crows,
            cdl_inverted_hammer, cdl_marubozu, cdl_inside_bar,
            cdl_outside_bar, cdl_spinning_top
        ]

    def calculate(self) -> pd.DataFrame:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                for pattern_func in self.pattern_functions:
                    self.df = pattern_func(self.df)
                    
            # جمع‌آوری همه الگوهای شناسایی شده برای آخرین کندل
            patterns_detected = []
            last_row = self.df.iloc[-1]
            for col in self.df.columns:
                if col.startswith('candlestick') and last_row[col]:
                    pattern_name = col.replace('candlestick_', '').replace('_', ' ').title()
                    patterns_detected.append(pattern_name)

            self.df[self.pattern_col] = "None"
            if patterns_detected:
                self.df.loc[self.df.index[-1], self.pattern_col] = ", ".join(patterns_detected)

        except Exception as e:
            logger.error(f"Error in candlestick pattern detection: {e}")
            self.df[self.pattern_col] = "Error"

        return self.df

    def analyze(self) -> dict:
        last_patterns = self.df.iloc[-1].get(self.pattern_col, "None")
        if last_patterns in ["None", "Error"] or pd.isna(last_patterns):
            return {"patterns": []}
        return {"patterns": [p.strip() for p in last_patterns.split(",")]}
