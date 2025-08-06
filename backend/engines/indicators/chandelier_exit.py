import pandas as pd
import numpy as np
import logging
from .base import BaseIndicator
from .atr import AtrIndicator # از اندیکاتور ATR که قبلا داشتیم استفاده می‌کنیم

logger = logging.getLogger(__name__)

class ChandelierExitIndicator(BaseIndicator):
    """
    پیاده‌سازی اندیکاتور Chandelier Exit برای تعیین حد ضرر داینامیک.
    این اندیکاتور از نوسانات بازار (ATR) برای تنظیم فاصله حد ضرر استفاده می‌کند.
    """

    def calculate(self) -> pd.DataFrame:
        """
        محاسبه خطوط Chandelier Exit برای پوزیشن‌های خرید (long) و فروش (short).

        Returns:
            pd.DataFrame: دیتافریم به‌روز شده با ستون‌های حد ضرر.
        """
        self.atr_period = self.params.get('atr_period', 22)
        self.atr_multiplier = self.params.get('atr_multiplier', 3.0)

        logger.debug(f"Calculating Chandelier Exit with atr_period={self.atr_period}, multiplier={self.atr_multiplier}")

        # --- محاسبه ATR ---
        # ما از کلاس AtrIndicator که از قبل در پروژه وجود دارد، به صورت بهینه استفاده می‌کنیم.
        # این کار از دوباره‌نویسی کد جلوگیری کرده و ماژولار بودن را تقویت می‌کند.
        atr_indicator = AtrIndicator(df=self.df, period=self.atr_period)
        self.df = atr_indicator.calculate()
        atr_col_name = f'atr_{self.atr_period}'

        # --- محاسبه بالاترین قیمت و پایین‌ترین قیمت در دوره ---
        highest_high = self.df['high'].rolling(window=self.atr_period).max()
        lowest_low = self.df['low'].rolling(window=self.atr_period).min()

        # --- محاسبه خطوط خروج ---
        self.long_stop_col = f'chandelier_long_stop_{self.atr_period}_{self.atr_multiplier}'
        self.short_stop_col = f'chandelier_short_stop_{self.atr_period}_{self.atr_multiplier}'

        self.df[self.long_stop_col] = highest_high - (self.df[atr_col_name] * self.atr_multiplier)
        self.df[self.short_stop_col] = lowest_low + (self.df[atr_col_name] * self.atr_multiplier)
        
        return self.df

    def analyze(self) -> dict:
        """
        تحلیل موقعیت قیمت نسبت به خطوط Chandelier Exit.
        این اندیکاتور ذاتا برای "خروج" طراحی شده است.

        Returns:
            dict: یک دیکشنری حاوی تحلیل نهایی.
        """
        last_row = self.df.iloc[-1]
        close_price = last_row['close']
        long_stop = last_row[self.long_stop_col]
        short_stop = last_row[self.short_stop_col]
        
        analysis = {
            'indicator': self.__class__.__name__,
            'params': {'atr_period': self.atr_period, 'multiplier': self.atr_multiplier},
            'values': {
                'close': close_price,
                'long_stop': round(long_stop, 4),
                'short_stop': round(short_stop, 4)
            }
        }

        # سیگنال فروش: قیمت زیر حد ضرر پوزیشن خرید بسته شده است
        if close_price < long_stop:
            analysis['signal'] = 'sell'
            analysis['message'] = "Price crossed below the Chandelier Exit (Long Stop). Exit long position."
        # سیگنال خرید: قیمت بالای حد ضرر پوزیشن فروش بسته شده است
        elif close_price > short_stop:
            analysis['signal'] = 'buy'
            analysis['message'] = "Price crossed above the Chandelier Exit (Short Stop). Exit short position."
        else:
            analysis['signal'] = 'neutral'
            analysis['message'] = "Price is holding between the Chandelier Exit stops. Hold position."
            
        return analysis
