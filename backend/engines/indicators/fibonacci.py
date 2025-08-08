import logging
import pandas as pd
from .base import BaseIndicator
from .zigzag import ZigzagIndicator

logger = logging.getLogger(__name__)

class FibonacciIndicator(BaseIndicator):
    """
    ✨ FINAL VERSION - JSON Safe ✨
    نسخه نهایی فیبوناچی هوشمند با خروجی سازگار با JSON.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.calculated_levels = {}
        self.trend = "N/A"
        self.swing_info = {}

    def calculate(self) -> pd.DataFrame:
        self.deviation_threshold = self.params.get('zigzag_deviation', 5.0)
        self.fib_levels_def = self.params.get('levels', [0, 23.6, 38.2, 50, 61.8, 78.6, 100])
        
        # ۱. استفاده از ZigzagIndicator برای پیدا کردن پیوت‌ها
        zigzag_indicator = ZigzagIndicator(self.df.copy(), deviation=self.deviation_threshold)
        zigzag_df = zigzag_indicator.calculate()
        
        pivot_col = f'zigzag_pivots_{self.deviation_threshold}'
        price_col = f'zigzag_prices_{self.deviation_threshold}'
        
        confirmed_pivots = zigzag_df[zigzag_df[pivot_col] != 0]
        
        if len(confirmed_pivots) < 2:
            return self.df

        last_pivot = confirmed_pivots.iloc[-1]
        prev_pivot = confirmed_pivots.iloc[-2]

        start_price = prev_pivot[price_col]
        end_price = last_pivot[price_col]
        price_diff = end_price - start_price
        
        if price_diff > 0: self.trend = "Up"
        else: self.trend = "Down"
            
        for level in self.fib_levels_def:
            level_price = end_price - (price_diff * (level / 100.0))
            self.calculated_levels[str(level)] = round(level_price, 5)

        # ✨ اصلاحیه کلیدی: تبدیل آبجکت‌های Timestamp به متن
        self.swing_info = {
            "start_price": start_price, 
            "start_time": prev_pivot.name.strftime('%Y-%m-%d %H:%M:%S'),
            "end_price": end_price, 
            "end_time": last_pivot.name.strftime('%Y-%m-%d %H:%M:%S')
        }
        return self.df

    def analyze(self) -> dict:
        return {
            'indicator': self.__class__.__name__,
            'trend_of_swing': self.trend,
            'levels': self.calculated_levels,
            'swing_info': self.swing_info
        }
