# engines/indicators/bollinger.py

import pandas as pd
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class BollingerIndicator(BaseIndicator):
    """
    کلاس محاسبه و تحلیل حرفه‌ای اندیکاتور Bollinger Bands.

    این ماژول علاوه بر محاسبه باندهای بالا، وسط و پایین، دو متریک کلیدی دیگر را نیز محاسبه و تحلیل می‌کند:
    - Bandwidth: برای شناسایی وضعیت فشردگی (Squeeze) و انبساط (Expansion).
    - %B (Percent B): برای تعیین موقعیت نسبی قیمت و شناسایی شکست‌های قیمتی.
    """

    def __init__(self, df: pd.DataFrame, period: int = 20, std_dev: int = 2):
        """
        سازنده کلاس Bollinger Bands.

        Args:
            df (pd.DataFrame): دیتافریم OHLCV.
            period (int): دوره زمانی برای محاسبه میانگین متحرک (باند وسط).
            std_dev (int): تعداد انحراف معیار برای محاسبه باندهای بالا و پایین.
        """
        super().__init__(df, period=period, std_dev=std_dev)
        self.period = period
        # تعریف نام ستون‌ها برای دسترسی آسان
        self.middle_col = f'bb_middle_{period}'
        self.upper_col = f'bb_upper_{period}'
        self.lower_col = f'bb_lower_{period}'
        self.width_col = f'bb_width_{period}'
        self.percent_b_col = f'bb_percent_b_{period}'

    def calculate(self) -> pd.DataFrame:
        """
        هر پنج مولفه بولینگر بندز را محاسبه کرده و به دیتافریم اضافه می‌کند.
        """
        # محاسبه باند وسط (میانگین متحرک ساده)
        self.df[self.middle_col] = self.df['close'].rolling(window=self.period).mean()
        
        # محاسبه انحراف معیار قیمت
        std = self.df['close'].rolling(window=self.period).std()
        
        # محاسبه باندهای بالا و پایین
        self.df[self.upper_col] = self.df[self.middle_col] + (std * self.params.get('std_dev', 2))
        self.df[self.lower_col] = self.df[self.middle_col] - (std * self.params.get('std_dev', 2))
        
        # --- محاسبات پیشرفته ---
        # 1. محاسبه پهنای باند (Bandwidth)
        # این متریک به ما می‌گوید باندها چقدر از هم باز یا به هم نزدیک هستند.
        self.df[self.width_col] = ((self.df[self.upper_col] - self.df[self.lower_col]) / self.df[self.middle_col]) * 100
        
        # 2. محاسبه درصد بی (Percent B)
        # این متریک موقعیت قیمت را نسبت به باندها نرمالایز می‌کند.
        self.df[self.percent_b_col] = (self.df['close'] - self.df[self.lower_col]) / (self.df[self.upper_col] - self.df[self.lower_col] + 1e-12)
        
        logger.debug("Calculated Bollinger Bands (Upper, Middle, Lower, Width, %B) successfully.")
        return self.df

    def analyze(self) -> dict:
        """
        آخرین وضعیت بولینگر بندز را تحلیل کرده و سیگنال‌های کلیدی را استخراج می‌کند.
        """
        required_cols = [self.upper_col, self.middle_col, self.lower_col, self.width_col, self.percent_b_col]
        if not all(col in self.df.columns and not self.df[col].isnull().all() for col in required_cols):
            raise ValueError("Bollinger Bands columns not found or are all NaN. Please run calculate() first.")

        last_row = self.df.iloc[-1]
        
        signal = "Neutral"

        # --- منطق پیشرفته تشخیص سیگنال ---

        # 1. تشخیص فشردگی (Squeeze)
        # اگر پهنای باند فعلی در ۱۰٪ پایین‌ترین مقادیر خود در ۱۲۰ کندل گذشته باشد، یک فشردگی در حال وقوع است.
        # این اغلب نشانه یک حرکت بزرگ در آینده است.
        lowest_width = self.df[self.width_col].rolling(window=120).min().iloc[-1]
        if last_row[self.width_col] <= lowest_width * 1.1: # 10% تلورانس
            signal = "Squeeze (Volatility Low)"

        # 2. تشخیص شکست (Breakout)
        # اگر قیمت از باند بالا خارج شود -> شکست صعودی
        if last_row[self.percent_b_col] > 1.0:
            signal = "Bullish Breakout"
        # اگر قیمت از باند پایین خارج شود -> شکست نزولی
        elif last_row[self.percent_b_col] < 0.0:
            signal = "Bearish Breakout"

        return {
            "upper_band": round(last_row[self.upper_col], 5),
            "middle_band": round(last_row[self.middle_col], 5),
            "lower_band": round(last_row[self.lower_col], 5),
            "bandwidth": round(last_row[self.width_col], 5),
            "percent_b": round(last_row[self.percent_b_col], 3),
            "signal": signal
        }
