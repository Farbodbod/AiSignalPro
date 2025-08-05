# engines/indicators/base.py

from abc import ABC, abstractmethod
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class BaseIndicator(ABC):
    """
    کلاس پایه انتزاعی (Abstract Base Class) برای تمام اندیکاتورهای تکنیکال.
    
    این کلاس یک "قرارداد" را تعریف می‌کند که هر اندیکاتور باید از آن پیروی کند.
    هر اندیکاتور مشتق شده باید دو متد اصلی را پیاده‌سازی کند:
    1. calculate(): برای انجام محاسبات ریاضی و افزودن نتایج به دیتافریم.
    2. analyze(): برای تحلیل آخرین مقدار محاسبه شده و ارائه یک تفسیر (سیگنال).
    """
    
    def __init__(self, df: pd.DataFrame, **kwargs):
        """
        سازنده کلاس.
        
        Args:
            df (pd.DataFrame): دیتافریم اصلی کندل‌ها (OHLCV).
                               یک کپی از آن برای جلوگیری از تغییرات ناخواسته (Side Effects) ذخیره می‌شود.
            **kwargs: پارامترهای اختیاری مخصوص هر اندیکاتور (مانند period, fast, slow و ...).
        """
        if df.empty:
            raise ValueError("Input DataFrame cannot be empty.")
        self.df = df.copy()  # کپی برای جلوگیری از تغییر دیتافریم اصلی در خارج از کلاس
        self.params = kwargs
        logger.debug(f"Initialized {self.__class__.__name__} with params: {self.params}")

    @abstractmethod
    def calculate(self) -> pd.DataFrame:
        """
        متد انتزاعی برای محاسبه اندیکاتور.
        
        این متد باید توسط هر کلاس فرزند پیاده‌سازی شود. وظیفه آن، افزودن یک یا چند
        ستون جدید حاوی مقادیر اندیکاتور به `self.df` است.
        
        Returns:
            pd.DataFrame: دیتافریم به‌روز شده با ستون(های) جدید اندیکاتور.
        """
        pass

    @abstractmethod
    def analyze(self) -> dict:
        """
        متد انتزاعی برای تحلیل نتیجه اندیکاتور.
        
        این متد باید آخرین مقدار اندیکاتور را از `self.df` خوانده و آن را تفسیر کند.
        خروجی باید یک دیکشنری استاندارد حاوی مقدار و سیگنال تولید شده باشد.
        
        Returns:
            dict: یک دیکشنری حاوی تحلیل نهایی.
                  مثال: {'value': 68.2, 'signal': 'Neutral'}
        """
        pass

