# engines/indicators/stochastic.py

import pandas as pd
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class StochasticIndicator(BaseIndicator):
    """
    کلاس محاسبه و تحلیل حرفه‌ای نوسانگر Stochastic.

    این ماژول دو خط اصلی %K (سریع) و %D (کند، که میانگین %K است) را محاسبه می‌کند
    و برای شناسایی وضعیت اشباع خرید/فروش و سیگنال‌های کراس‌اوور استفاده می‌شود.
    """

    def __init__(self, df: pd.DataFrame, k_period: int = 14, d_period: int = 3, smooth_k: int = 3):
        """
        سازنده کلاس Stochastic.

        Args:
            df (pd.DataFrame): دیتافریم OHLCV.
            k_period (int): دوره زمانی برای پیدا کردن بالاترین و پایین‌ترین قیمت.
            d_period (int): دوره زمانی برای میانگین متحرک خط %K (برای ساخت %D).
            smooth_k (int): دوره زمانی برای هموارسازی اولیه خط %K (برای ساخت استوکاستیک کند).
        """
        super().__init__(df, k_period=k_period, d_period=d_period, smooth_k=smooth_k)
        self.k_col = f'stoch_k_{k_period}_{d_period}'
        self.d_col = f'stoch_d_{k_period}_{d_period}'

    def calculate(self) -> pd.DataFrame:
        """
        محاسبه خطوط %K و %D استوکاستیک.
        """
        k_period = self.params.get('k_period', 14)
        d_period = self.params.get('d_period', 3)
        smooth_k = self.params.get('smooth_k', 3)

        # ۱. پیدا کردن پایین‌ترین قیمت در دوره k_period
        low_min = self.df['low'].rolling(window=k_period).min()
        # ۲. پیدا کردن بالاترین قیمت در دوره k_period
        high_max = self.df['high'].rolling(window=k_period).max()

        # ۳. محاسبه خط %K خام (Fast %K)
        fast_k = 100 * ((self.df['close'] - low_min) / (high_max - low_min + 1e-12))
        
        # ۴. هموارسازی %K برای ساخت %K نهایی (Slow %K) - این همان خطی است که معمولاً نمایش داده می‌شود
        self.df[self.k_col] = fast_k.rolling(window=smooth_k).mean()
        
        # ۵. محاسبه خط %D با گرفتن میانگین از %K نهایی
        self.df[self.d_col] = self.df[self.k_col].rolling(window=d_period).mean()

        logger.debug("Calculated Stochastic %K and %D successfully.")
        return self.df

    def analyze(self) -> dict:
        """
        آخرین وضعیت استوکاستیک را تحلیل کرده و سیگنال‌های کراس‌اوور و وضعیت اشباع را مشخص می‌کند.
        """
        required_cols = [self.k_col, self.d_col]
        if not all(col in self.df.columns and not self.df[col].isnull().all() for col in required_cols):
            raise ValueError("Stochastic columns not found or are all NaN. Please run calculate() first.")

        last_row = self.df.iloc[-1]
        prev_row = self.df.iloc[-2]

        k_val = last_row[self.k_col]
        d_val = last_row[self.d_col]

        # تعیین وضعیت اشباع
        position = "Neutral Zone"
        if k_val > 80 and d_val > 80:
            position = "Overbought"
        elif k_val < 20 and d_val < 20:
            position = "Oversold"
        
        signal = "Neutral"
        # تشخیص کراس‌اوور
        if prev_row[self.k_col] < prev_row[self.d_col] and k_val > d_val:
            # اگر کراس در ناحیه اشباع فروش باشد، سیگنال بسیار قوی‌تر است
            if prev_row[self.k_col] < 30: # کمی بالاتر از ۲۰ برای شکار زودتر
                signal = "Strong Bullish Crossover"
            else:
                signal = "Bullish Crossover"
        elif prev_row[self.k_col] > prev_row[self.d_col] and k_val < d_val:
            # اگر کراس در ناحیه اشباع خرید باشد، سیگنال بسیار قوی‌تر است
            if prev_row[self.k_col] > 70: # کمی پایین‌تر از ۸۰
                signal = "Strong Bearish Crossover"
            else:
                signal = "Bearish Crossover"

        return {
            "percent_k": round(k_val, 2),
            "percent_d": round(d_val, 2),
            "position": position,
            "signal": signal
        }
