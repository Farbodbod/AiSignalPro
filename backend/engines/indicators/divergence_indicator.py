# engines/indicators/divergence_indicator.py

import pandas as pd
import numpy as np
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class DivergenceIndicator(BaseIndicator):
    """
    ماژول پیشرفته برای شناسایی واگرایی‌های صعودی و نزولی بین قیمت و RSI.
    این ماژول به دنبال نقاط واگرایی در پیوت‌های قیمتی می‌گردد.
    """

    def __init__(self, df: pd.DataFrame, period: int = 14, lookback: int = 30):
        """
        سازنده کلاس.

        Args:
            df (pd.DataFrame): دیتافریم OHLCV که باید شامل ستون RSI باشد.
            period (int): دوره زمانی RSI که برای واگرایی استفاده می‌شود.
            lookback (int): تعداد کندل‌هایی که برای یافتن پیوت‌ها به عقب نگاه می‌کنیم.
        """
        super().__init__(df, period=period, lookback=lookback)
        self.rsi_col = f'rsi_{period}'
        self.lookback = lookback

    def calculate(self) -> pd.DataFrame:
        """
        این اندیکاتور ستون جدیدی اضافه نمی‌کند، فقط دیتافریم را برای تحلیل آماده می‌کند.
        ما فرض می‌کنیم که RSI قبلاً توسط RsiIndicator محاسبه و به df اضافه شده است.
        """
        if self.rsi_col not in self.df.columns:
            logger.warning(f"'{self.rsi_col}' not found in DataFrame. RSI must be calculated before checking for divergence.")
            # برای جلوگیری از خطا، یک ستون خالی ایجاد می‌کنیم
            self.df[self.rsi_col] = 50 
        return self.df

    def _find_pivots(self, series: pd.Series, pivot_type: str) -> list:
        """یک متد داخلی برای یافتن نقاط پیوت (سقف یا کف) در یک سری داده."""
        pivots = []
        # ما در بازه lookback به دنبال پیوت‌ها می‌گردیم
        data = series.tail(self.lookback)
        
        for i in range(5, len(data) - 5): # از حاشیه‌ها فاصله می‌گیریم
            is_pivot = False
            window = data.iloc[i-5:i+6]
            
            if pivot_type == 'high' and data.iloc[i] == window.max():
                is_pivot = True
            elif pivot_type == 'low' and data.iloc[i] == window.min():
                is_pivot = True
            
            if is_pivot:
                # ایندکس و مقدار پیوت را ذخیره می‌کنیم
                pivots.append((data.index[i], data.iloc[i]))
        
        # حذف پیوت‌های تکراری و نزدیک به هم
        if not pivots: return []
        unique_pivots = [pivots[0]]
        for i in range(1, len(pivots)):
            if pivots[i][1] != unique_pivots[-1][1]:
                unique_pivots.append(pivots[i])
        
        return unique_pivots

    def analyze(self) -> dict:
        """
        منطق اصلی برای شناسایی واگرایی بین دو پیوت آخر.
        """
        rsi_series = self.df[self.rsi_col]
        price_high_series = self.df['high']
        price_low_series = self.df['low']

        # یافتن آخرین پیوت‌های سقف
        price_highs = self._find_pivots(price_high_series, 'high')
        rsi_highs = self._find_pivots(rsi_series, 'high')

        # یافتن آخرین پیوت‌های کف
        price_lows = self._find_pivots(price_low_series, 'low')
        rsi_lows = self._find_pivots(rsi_series, 'low')
        
        result = {"type": "None", "strength": "Normal"}

        # ۱. بررسی واگرایی نزولی (Bearish Divergence)
        if len(price_highs) >= 2 and len(rsi_highs) >= 2:
            # آخرین دو سقف قیمت و RSI
            last_price_high = price_highs[-1][1]
            prev_price_high = price_highs[-2][1]
            last_rsi_high = rsi_highs[-1][1]
            prev_rsi_high = rsi_highs[-2][1]

            if (last_price_high > prev_price_high) and (last_rsi_high < prev_rsi_high):
                result["type"] = "Bearish"
                # اگر واگرایی در ناحیه اشباع خرید باشد، قوی‌تر است
                if last_rsi_high > 70:
                    result["strength"] = "Strong"

        # ۲. بررسی واگرایی صعودی (Bullish Divergence)
        if len(price_lows) >= 2 and len(rsi_lows) >= 2:
            # آخرین دو کف قیمت و RSI
            last_price_low = price_lows[-1][1]
            prev_price_low = price_lows[-2][1]
            last_rsi_low = rsi_lows[-1][1]
            prev_rsi_low = rsi_lows[-2][1]

            if (last_price_low < prev_price_low) and (last_rsi_low > prev_rsi_low):
                result["type"] = "Bullish"
                # اگر واگرایی در ناحیه اشباع فروش باشد، قوی‌تر است
                if last_rsi_low < 30:
                    result["strength"] = "Strong"
        
        return result
