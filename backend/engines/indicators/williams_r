import pandas as pd
import numpy as np
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class WilliamsRIndicator(BaseIndicator):
    """
    پیاده‌سازی اندیکاتور Williams %R، یک اسیلاتور مومنتوم برای شناسایی
    نواحی اشباع خرید و فروش.
    """

    def calculate(self) -> pd.DataFrame:
        """
        محاسبه مقدار اندیکاتور Williams %R.

        Returns:
            pd.DataFrame: دیتافریم به‌روز شده با ستون اندیکاتور.
        """
        self.period = self.params.get('period', 14)
        self.overbought_level = self.params.get('overbought', -20)
        self.oversold_level = self.params.get('oversold', -80)

        logger.debug(f"Calculating Williams %R with period={self.period}")
        
        # --- محاسبه بالاترین قیمت و پایین‌ترین قیمت در دوره ---
        highest_high = self.df['high'].rolling(window=self.period).max()
        lowest_low = self.df['low'].rolling(window=self.period).min()

        self.col_name = f'williams_r_{self.period}'
        
        # --- اعمال فرمول و مدیریت تقسیم بر صفر ---
        # (Highest High - Close) / (Highest High - Lowest Low) * -100
        numerator = highest_high - self.df['close']
        denominator = highest_high - lowest_low
        
        # برای جلوگیری از تقسیم بر صفر، جایی که high == low است
        self.df[self.col_name] = np.where(
            denominator == 0,
            -50,  # یک مقدار میانی و خنثی
            (numerator / denominator) * -100
        )
        
        return self.df

    def analyze(self) -> dict:
        """
        تحلیل مقدار Williams %R برای سیگنال‌دهی بر اساس خروج از نواحی اشباع.

        Returns:
            dict: یک دیکشنری حاوی تحلیل نهایی.
        """
        if len(self.df) < 2:
            return {'signal': 'neutral', 'message': 'Not enough data for analysis.'}
            
        last_value = self.df[self.col_name].iloc[-1]
        prev_value = self.df[self.col_name].iloc[-2]
        
        analysis = {
            'indicator': self.__class__.__name__,
            'params': {'period': self.period, 'ob': self.overbought_level, 'os': self.oversold_level},
            'values': {
                'williams_r': round(last_value, 2)
            }
        }

        # سیگنال خرید: عبور از پایین به بالای خط اشباع فروش
        if prev_value <= self.oversold_level and last_value > self.oversold_level:
            analysis['signal'] = 'buy'
            analysis['message'] = f"Williams %R crossed above the oversold level ({self.oversold_level}). Potential bullish reversal."
        # سیگنال فروش: عبور از بالا به پایین خط اشباع خرید
        elif prev_value >= self.overbought_level and last_value < self.overbought_level:
            analysis['signal'] = 'sell'
            analysis['message'] = f"Williams %R crossed below the overbought level ({self.overbought_level}). Potential bearish reversal."
        else:
            analysis['signal'] = 'neutral'
            if last_value <= self.oversold_level:
                analysis['message'] = "Williams %R is in the oversold zone."
            elif last_value >= self.overbought_level:
                analysis['message'] = "Williams %R is in the overbought zone."
            else:
                analysis['message'] = "Williams %R is in a neutral zone."
            
        return analysis

