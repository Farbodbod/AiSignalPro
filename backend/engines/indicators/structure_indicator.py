import numpy as np
import pandas as pd
from typing import List, Dict, Any
from .base import BaseIndicator
from .zigzag import ZigzagIndicator # ✨ 1. استفاده از ZigZag برای پیوت‌ها
import logging

logger = logging.getLogger(__name__)

class StructureIndicator(BaseIndicator):
    """
    ✨ UPGRADE v2.0 ✨
    - Pivot detection re-engineered to use the robust ZigzagIndicator.
    - Provides more reliable and consistent S/R levels.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.zigzag_deviation = self.params.get('zigzag_deviation', 5.0)

    def calculate(self) -> pd.DataFrame:
        # این اندیکاتور تنها به محاسبات ZigZag به عنوان پیش‌نیاز نیاز دارد
        if f'zigzag_pivots_{self.zigzag_deviation}' not in self.df.columns:
            zigzag_indicator = ZigzagIndicator(self.df, deviation=self.zigzag_deviation)
            self.df = zigzag_indicator.calculate()
        return self.df

    def analyze(self) -> dict:
        zigzag_pivots_col = f'zigzag_pivots_{self.zigzag_deviation}'
        zigzag_prices_col = f'zigzag_prices_{self.zigzag_deviation}'
        
        pivots_df = self.df[self.df[zigzag_pivots_col] != 0]
        
        supports = sorted(list(set(pivots_df[pivots_df[zigzag_pivots_col] == -1][zigzag_prices_col])), reverse=True)
        resistances = sorted(list(set(pivots_df[pivots_df[zigzag_pivots_col] == 1][zigzag_prices_col])))

        key_levels = {
            'supports': supports[:5],      # ۵ سطح حمایت کلیدی آخر
            'resistances': resistances[:5] # ۵ سطح مقاومت کلیدی آخر
        }
        
        return {
            "pivots_count": len(pivots_df),
            "key_levels": key_levels
        }
