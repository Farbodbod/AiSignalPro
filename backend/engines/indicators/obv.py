# engines/indicators/obv.py

import pandas as pd
import numpy as np
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class ObvIndicator(BaseIndicator):
    """
    کلاس محاسبه و تحلیل حرفه‌ای اندیکاتور On-Balance Volume (OBV).

    این ماژول جریان تجمعی حجم را بر اساس حرکات قیمت اندازه‌گیری می‌کند.
    برای افزایش دقت، یک میانگین متحرک از خود OBV نیز محاسبه و تحلیل می‌شود
    تا روند جریان حجم و واگرایی‌های احتمالی شناسایی شوند.
    """

    def __init__(self, df: pd.DataFrame, ma_period: int = 20):
        """
        سازنده کلاس OBV.

        Args:
            df (pd.DataFrame): دیتافریم OHLCV.
            ma_period (int): دوره زمانی برای محاسبه میانگین متحرک خط OBV.
        """
        super().__init__(df, ma_period=ma_period)
        self.ma_period = ma_period
        self.obv_col = 'obv'
        self.obv_ma_col = f'obv_ma_{ma_period}'

    def calculate(self) -> pd.DataFrame:
        """
        محاسبه خط OBV و میانگین متحرک آن.
        """
        # ۱. محاسبه OBV
        # اگر قیمت بسته شدن فعلی بالاتر از قبلی باشد، حجم اضافه می‌شود.
        # اگر پایین‌تر باشد، حجم کم می‌شود. در غیر این صورت، OBV ثابت می‌ماند.
        obv = np.where(self.df['close'] > self.df['close'].shift(1), self.df['volume'], 
              np.where(self.df['close'] < self.df['close'].shift(1), -self.df['volume'], 0)).cumsum()
        
        self.df[self.obv_col] = obv
        
        # ۲. محاسبه میانگین متحرک ساده از خط OBV
        self.df[self.obv_ma_col] = self.df[self.obv_col].rolling(window=self.ma_period).mean()
        
        logger.debug("Calculated OBV and OBV Moving Average successfully.")
        return self.df

    def analyze(self) -> dict:
        """
        آخرین وضعیت OBV را تحلیل کرده و روند جریان حجم را مشخص می‌کند.
        کراس بین OBV و میانگین متحرک آن می‌تواند نشانه تغییر در فشار خرید/فروش باشد.
        """
        required_cols = [self.obv_col, self.obv_ma_col]
        if not all(col in self.df.columns and not self.df[col].isnull().all() for col in required_cols):
            raise ValueError("OBV columns not found or are all NaN. Please run calculate() first.")
            
        last_row = self.df.iloc[-1]
        prev_row = self.df.iloc[-2]

        obv_value = last_row[self.obv_col]
        obv_ma_value = last_row[self.obv_ma_col]

        # تعیین روند کلی بر اساس موقعیت OBV نسبت به میانگینش
        trend = "Bullish Momentum" if obv_value > obv_ma_value else "Bearish Momentum"
        signal = "Volume Trend Continuation"

        # تشخیص کراس‌اوور به عنوان یک سیگنال قوی‌تر
        if prev_row[self.obv_col] < prev_row[self.obv_ma_col] and obv_value > obv_ma_value:
            signal = "Bullish Volume Crossover"
        elif prev_row[self.obv_col] > prev_row[self.obv_ma_col] and obv_value < obv_ma_value:
            signal = "Bearish Volume Crossover"
            
        # واگرایی (Divergence) یک مفهوم پیشرفته‌تر است که نیاز به مقایسه روند قیمت و روند OBV دارد.
        # در این تحلیل اولیه، ما بر روی سیگنال‌های مستقیم تمرکز می‌کنیم.

        return {
            "obv_value": int(obv_value),
            "obv_ma_value": int(obv_ma_value),
            "trend": trend,
            "signal": signal
        }
