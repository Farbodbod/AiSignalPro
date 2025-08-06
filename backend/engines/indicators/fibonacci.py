import logging
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np
from .base import BaseIndicator
from .zigzag import ZigzagIndicator

logger = logging.getLogger(__name__)

class FibonacciIndicator(BaseIndicator):
    """
    یک اندیکاتور هوشمند که به صورت خودکار آخرین حرکت مهم بازار (Swing) را
    با استفاده از ZigZag شناسایی کرده و سطوح بازگشتی فیبوناچی را محاسبه می‌کند.
    """

    def calculate(self) -> pd.DataFrame:
        """
        محاسبه سطوح فیبوناچی. این اندیکاتور ستونی به دیتافریم اضافه نمی‌کند،
        بلکه نتیجه را در یک متغیر داخلی برای استفاده در `analyze` ذخیره می‌کند.
        """
        self.deviation_threshold = self.params.get('zigzag_deviation', 5.0)
        self.fib_levels_def = self.params.get('levels', [0, 23.6, 38.2, 50, 61.8, 78.6, 100])
        
        logger.debug(f"Calculating Fibonacci levels based on ZigZag with deviation={self.deviation_threshold}%")

        # 1. استفاده از ZigzagIndicator برای پیدا کردن پیوت‌ها
        zigzag_indicator = ZigzagIndicator(df=self.df, deviation=self.deviation_threshold)
        zigzag_df = zigzag_indicator.calculate()
        
        pivot_col = f'zigzag_pivots_{self.deviation_threshold}'
        price_col = f'zigzag_prices_{self.deviation_threshold}'
        
        # 2. پیدا کردن دو پیوت آخر
        confirmed_pivots = zigzag_df[zigzag_df[pivot_col] != 0]
        
        self.calculated_levels = {} # ریست کردن سطوح
        self.trend = "N/A"

        if len(confirmed_pivots) < 2:
            logger.info("Not enough pivots to draw Fibonacci levels.")
            return self.df # بازگرداندن دیتافریم اصلی بدون تغییر

        last_pivot = confirmed_pivots.iloc[-1]
        prev_pivot = confirmed_pivots.iloc[-2]

        start_price = prev_pivot[price_col]
        end_price = last_pivot[price_col]
        
        # 3. محاسبه سطوح فیبوناچی
        price_diff = end_price - start_price
        
        if price_diff > 0:
            self.trend = "Up" # آخرین حرکت صعودی بوده (منتظر بازگشت نزولی)
        else:
            self.trend = "Down" # آخرین حرکت نزولی بوده (منتظر بازگشت صعودی)
            
        for level in self.fib_levels_def:
            # فرمول محاسبه سطح فیبوناچی
            level_price = end_price - (price_diff * (level / 100.0))
            self.calculated_levels[str(level)] = round(level_price, 5)

        self.swing_info = {
            "start_price": start_price, "start_time": prev_pivot.name,
            "end_price": end_price, "end_time": last_pivot.name
        }

        return self.df

    def analyze(self) -> dict:
        """
        تحلیل و ارائه سطوح فیبوناچی محاسبه شده.
        """
        return {
            'indicator': self.__class__.__name__,
            'trend_of_swing': self.trend,
            'levels': self.calculated_levels,
            'swing_info': self.swing_info if hasattr(self, 'swing_info') else {}
        }
