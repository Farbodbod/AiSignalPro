# engines/indicators/macd.py

import pandas as pd
import numpy as np
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class MacdIndicator(BaseIndicator):
    """
    کلاس محاسبه و تحلیل اندیکاتور Moving Average Convergence Divergence (MACD).
    این کلاس سیگنال‌های کلیدی MACD مانند کراس‌اوور خط سیگنال و کراس‌اوور خط صفر را شناسایی می‌کند.
    """

    def __init__(self, df: pd.DataFrame, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9):
        """
        سازنده کلاس MACD.

        Args:
            df (pd.DataFrame): دیتافریم OHLCV.
            fast_period (int): دوره زمانی برای میانگین متحرک نمایی سریع (پیش‌فرض ۱۲).
            slow_period (int): دوره زمانی برای میانگین متحرک نمایی کند (پیش‌فرض ۲۶).
            signal_period (int): دوره زمانی برای خط سیگنال (پیش‌فرض ۹).
        """
        super().__init__(df, fast_period=fast_period, slow_period=slow_period, signal_period=signal_period)
        self.fast_col = f'ema_{fast_period}'
        self.slow_col = f'ema_{slow_period}'
        self.macd_col = 'macd_line'
        self.signal_col = 'macd_signal'
        self.hist_col = 'macd_hist'

    def calculate(self) -> pd.DataFrame:
        """
        مقادیر خط MACD، خط سیگنال و هیستوگرام را محاسبه کرده و به دیتافریم اضافه می‌کند.
        """
        # استخراج پارامترها
        fast = self.params.get('fast_period', 12)
        slow = self.params.get('slow_period', 26)
        signal = self.params.get('signal_period', 9)

        # محاسبه دو میانگین متحرک نمایی
        ema_fast = self.df['close'].ewm(span=fast, adjust=False).mean()
        ema_slow = self.df['close'].ewm(span=slow, adjust=False).mean()

        # محاسبه خط MACD
        self.df[self.macd_col] = ema_fast - ema_slow
        # محاسبه خط سیگنال
        self.df[self.signal_col] = self.df[self.macd_col].ewm(span=signal, adjust=False).mean()
        # محاسبه هیستوگرام
        self.df[self.hist_col] = self.df[self.macd_col] - self.df[self.signal_col]
        
        logger.debug("Calculated MACD, Signal Line, and Histogram successfully.")
        return self.df

    def analyze(self) -> dict:
        """
        آخرین وضعیت MACD را تحلیل کرده و سیگنال‌های کراس‌اوور را شناسایی می‌کند.
        """
        # اطمینان از اینکه محاسبات انجام شده است
        required_cols = [self.macd_col, self.signal_col, self.hist_col]
        if not all(col in self.df.columns for col in required_cols):
            raise ValueError("MACD columns not found. Please run calculate() first.")

        # استخراج دو کندل آخر برای تشخیص کراس‌اوور
        last_row = self.df.iloc[-1]
        prev_row = self.df.iloc[-2]

        signal = "Neutral"

        # --- منطق پیشرفته تشخیص سیگنال ---

        # 1. تشخیص کراس‌اوور خط MACD و خط سیگنال
        # اگر در کندل قبل، خط مکدی زیر خط سیگنال بوده و در کندل فعلی بالای آن قرار گرفته -> سیگنال خرید
        if prev_row[self.macd_col] < prev_row[self.signal_col] and last_row[self.macd_col] > last_row[self.signal_col]:
            signal = "Bullish Crossover"
        # اگر در کندل قبل، خط مکدی بالای خط سیگنال بوده و در کندل فعلی زیر آن قرار گرفته -> سیگنال فروش
        elif prev_row[self.macd_col] > prev_row[self.signal_col] and last_row[self.macd_col] < last_row[self.signal_col]:
            signal = "Bearish Crossover"

        # 2. تشخیص کراس‌اوور خط صفر (Centerline Crossover) - سیگنال قوی‌تر
        # اگر خط مکدی از زیر صفر به بالای صفر رفته باشد -> نشانه شروع روند صعودی
        elif prev_row[self.macd_col] < 0 and last_row[self.macd_col] > 0:
            signal = "Bullish Centerline Cross"
        # اگر خط مکدی از بالای صفر به زیر صفر رفته باشد -> نشانه شروع روند نزولی
        elif prev_row[self.macd_col] > 0 and last_row[self.macd_col] < 0:
            signal = "Bearish Centerline Cross"

        return {
            "macd_line": round(last_row[self.macd_col], 5),
            "signal_line": round(last_row[self.signal_col], 5),
            "histogram": round(last_row[self.hist_col], 5),
            "signal": signal
        }
