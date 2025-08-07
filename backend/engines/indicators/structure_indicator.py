import numpy as np
import pandas as pd
from typing import List, Dict, Any
from .base import BaseIndicator
from .zigzag import ZigzagIndicator
import logging

logger = logging.getLogger(__name__)

class StructureIndicator(BaseIndicator):
    """
    ✨ UPGRADE v2.1 - State Reset Fix ✨
    - Pivot list is now correctly reset on each calculation.
    - Ensures fresh and relevant S/R levels for every analysis.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.zigzag_deviation = self.params.get('zigzag_deviation', 5.0)

    def calculate(self) -> pd.DataFrame:
        # این اندیکاتور تنها به محاسبات ZigZag به عنوان پیش‌نیاز نیاز دارد
        if f'zigzag_pivots_{self.zigzag_deviation}' not in self.df.columns:
            # یک کپی از دیتافریم را برای جلوگیری از تداخل ارسال می‌کنیم
            zigzag_indicator = ZigzagIndicator(self.df.copy(), deviation=self.zigzag_deviation)
            # نتیجه محاسبه را به دیتافریم اصلی خودمان اعمال می‌کنیم
            self.df = zigzag_indicator.calculate()
        return self.df

    def analyze(self) -> dict:
        zigzag_pivots_col = f'zigzag_pivots_{self.zigzag_deviation}'
        zigzag_prices_col = f'zigzag_prices_{self.zigzag_deviation}'
        
        # ✨ اصلاحیه کلیدی: ما هر بار تحلیل را روی دیتافریم تمیز انجام می‌دهیم
        # و هیچ داده‌ای از تحلیل‌های قبلی باقی نمی‌ماند.
        pivots_df = self.df[self.df[zigzag_pivots_col] != 0]
        
        if pivots_df.empty:
            return {"pivots_count": 0, "key_levels": {"supports": [], "resistances": []}}

        supports = sorted(list(set(pivots_df[pivots_df[zigzag_pivots_col] == -1][zigzag_prices_col])), reverse=True)
        resistances = sorted(list(set(pivots_df[pivots_df[zigzag_pivots_col] == 1][zigzag_prices_col])))

        key_levels = {
            'supports': [round(s, 5) for s in supports[:5]],      # ۵ سطح حمایت کلیدی آخر
            'resistances': [round(r, 5) for r in resistances[:5]] # ۵ سطح مقاومت کلیدی آخر
        }
        
        return {
            "pivots_count": len(pivots_df),
            "key_levels": key_levels
        }
