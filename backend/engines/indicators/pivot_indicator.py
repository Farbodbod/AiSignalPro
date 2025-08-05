# engines/indicators/pivot_indicator.py

import pandas as pd
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class PivotPointIndicator(BaseIndicator):
    """
    ماژول پیشرفته برای محاسبه و تحلیل سطوح پیوت پوینت با متدهای مختلف.
    این اندیکاتور یک اندیکاتور پیشرو (Leading) است که سطوح حمایت و مقاومت بالقوه
    را برای دوره زمانی فعلی، بر اساس داده‌های دوره زمانی قبلی محاسبه می‌کند.
    """

    def __init__(self, df: pd.DataFrame, method: str = 'standard', **kwargs):
        """
        سازنده کلاس.
        Args:
            df (pd.DataFrame): دیتافریم OHLCV.
            method (str): متد محاسبه ('standard', 'fibonacci', 'camarilla').
        """
        super().__init__(df, method=method, **kwargs)
        if len(df) < 2:
            raise ValueError("Pivot Points require at least 2 data points (previous and current).")
        self.method = method
        self.pivots = {}

    def calculate(self) -> pd.DataFrame:
        """
        سطوح پیوت را بر اساس کندل قبلی محاسبه کرده و در خود ذخیره می‌کند.
        این اندیکاتور ستون جدیدی به کل دیتافریم اضافه نمی‌کند.
        """
        # ما از کندل دوم به آخر (کندل قبلی) برای محاسبات استفاده می‌کنیم.
        prev_candle = self.df.iloc[-2]
        high = prev_candle['high']
        low = prev_candle['low']
        close = prev_candle['close']
        
        # محاسبه پیوت اصلی (P)
        pivot = (high + low + close) / 3
        
        if self.method == 'fibonacci':
            self._calculate_fibonacci(pivot, high, low)
        elif self.method == 'camarilla':
            self._calculate_camarilla(pivot, high, low, close)
        else: # standard
            self._calculate_standard(pivot, high, low)
        
        return self.df

    def _calculate_standard(self, p, h, l):
        r1 = (2 * p) - l
        s1 = (2 * p) - h
        r2 = p + (h - l)
        s2 = p - (h - l)
        r3 = h + 2 * (p - l)
        s3 = l - 2 * (h - p)
        self.pivots = {'R3': r3, 'R2': r2, 'R1': r1, 'P': p, 'S1': s1, 'S2': s2, 'S3': s3}

    def _calculate_fibonacci(self, p, h, l):
        r = h - l
        r3 = p + (r * 1.000)
        r2 = p + (r * 0.618)
        r1 = p + (r * 0.382)
        s1 = p - (r * 0.382)
        s2 = p - (r * 0.618)
        s3 = p - (r * 1.000)
        self.pivots = {'R3': r3, 'R2': r2, 'R1': r1, 'P': p, 'S1': s1, 'S2': s2, 'S3': s3}

    def _calculate_camarilla(self, p, h, l, c):
        r = h - l
        r4 = c + (r * 1.1 / 2)
        r3 = c + (r * 1.1 / 4)
        r2 = c + (r * 1.1 / 6)
        r1 = c + (r * 1.1 / 12)
        s1 = c - (r * 1.1 / 12)
        s2 = c - (r * 1.1 / 6)
        s3 = c - (r * 1.1 / 4)
        s4 = c - (r * 1.1 / 2)
        self.pivots = {'R4': r4, 'R3': r3, 'R2': r2, 'R1': r1, 'P': p, 'S1': s1, 'S2': s2, 'S3': s3, 'S4': s4}

    def analyze(self) -> dict:
        """
        موقعیت قیمت فعلی را نسبت به سطوح پیوت محاسبه شده تحلیل می‌کند.
        """
        if not self.pivots:
            # اگر محاسبات انجام نشده، دوباره اجرا کن
            self.calculate()
        
        current_price = self.df.iloc[-1]['close']
        
        position = "Unknown"
        # پیدا کردن نزدیک‌ترین سطح بالا و پایین به قیمت فعلی
        sorted_levels = sorted(self.pivots.items(), key=lambda item: item[1])
        
        above = None
        below = None
        
        for name, level in sorted_levels:
            if level > current_price:
                above = (name, level)
                break
        
        for name, level in reversed(sorted_levels):
            if level < current_price:
                below = (name, level)
                break
        
        if above and below:
            position = f"Between {below[0]} and {above[0]}"
        elif above:
            position = f"Above all pivots, approaching {above[0]}"
        elif below:
            position = f"Below all pivots, testing {below[0]}"

        # بررسی اینکه آیا قیمت به یکی از سطوح بسیار نزدیک است یا خیر
        for name, level in self.pivots.items():
            if abs(current_price - level) / current_price < 0.001: # نزدیک‌تر از ۰.۱٪
                position = f"Testing {name}"
                break
        
        analysis_result = {"levels": self.pivots, "position": position}
        return analysis_result
