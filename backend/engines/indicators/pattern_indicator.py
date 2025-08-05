# engines/indicators/pattern_indicator.py

import pandas as pd
import talib # ما از کتابخانه قدرتمند TA-Lib برای شناسایی الگوها استفاده می‌کنیم
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class PatternIndicator(BaseIndicator):
    """
    این ماژول، تمام الگوهای شمعی شناخته‌شده را با استفاده از کتابخانه TA-Lib
    بر روی دیتافریم شناسایی می‌کند.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        # این اندیکاتور پارامتر خاصی ندارد، اما ساختار را حفظ می‌کنیم
        super().__init__(df, **kwargs)
        self.pattern_col = 'identified_pattern'

    def calculate(self) -> pd.DataFrame:
        """
        تمام توابع شناسایی الگو از TA-Lib را اجرا کرده و نتایج را در یک ستون ذخیره می‌کند.
        """
        # لیست تمام توابع تشخیص الگو در TA-Lib که با 'CDL' شروع می‌شوند
        pattern_functions = [func for func in dir(talib) if func.startswith('CDL')]
        
        # یک ستون جدید برای نام الگو ایجاد می‌کنیم و مقدار اولیه آن را "None" می‌گذاریم
        self.df[self.pattern_col] = "None"
        
        # روی تمام توابع الگو در کتابخانه حلقه می‌زنیم
        for func_name in pattern_functions:
            try:
                pattern_function = getattr(talib, func_name)
                # اجرای تابع بر روی داده‌های OHLC
                result = pattern_function(self.df['open'], self.df['high'], self.df['low'], self.df['close'])
                
                # نتیجه غیر صفر نشان‌دهنده وجود الگو در کندل مربوطه است
                # ما فقط به آخرین کندل اهمیت می‌دهیم
                if result.iloc[-1] != 0:
                    pattern_name = func_name.replace('CDL', '') # حذف پیشوند 'CDL' برای خوانایی
                    
                    # اگر قبلاً الگویی در همین کندل پیدا شده، الگوی جدید را با کاما به آن اضافه می‌کنیم
                    if self.df[self.pattern_col].iloc[-1] != "None":
                        # استفاده از .loc برای تخصیص مقدار به صورت ایمن
                        self.df.loc[self.df.index[-1], self.pattern_col] += f", {pattern_name}"
                    else:
                        self.df.loc[self.df.index[-1], self.pattern_col] = pattern_name

            except Exception as e:
                # در صورت بروز خطا برای یک الگو، از آن رد شده و به کار ادامه می‌دهیم
                logger.warning(f"Could not run pattern function {func_name}: {e}")

        return self.df

    def analyze(self) -> dict:
        """
        نام الگوی(های) شناسایی شده در آخرین کندل را به صورت یک لیست برمی‌گرداند.
        """
        last_patterns_str = self.df[self.pattern_col].iloc[-1]
        
        # اگر هیچ الگویی پیدا نشده باشد، لیست خالی برمی‌گردانیم
        if last_patterns_str == "None":
            return {"patterns": []}
        
        # رشته الگوها را با کاما جدا کرده و به صورت لیست برمی‌گردانیم
        return {"patterns": [p.strip() for p in last_patterns_str.split(',')]}

