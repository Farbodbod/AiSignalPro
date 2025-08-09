from abc import ABC, abstractmethod
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class BaseIndicator(ABC):
    """
    کلاس پایه انتزاعی (Abstract Base Class) برای تمام اندیکاتورهای AiSignalPro.
    این کلاس یک "قرارداد" استاندارد برای تمام اندیکاتورها تعریف می‌کند تا از
    یکپارچگی و قابلیت اطمینان کل سیستم اطمینان حاصل شود.
    """
    
    def __init__(self, df: pd.DataFrame, **kwargs):
        """
        سازنده کلاس.
        
        Args:
            df (pd.DataFrame): دیتافریم اصلی کندل‌ها (OHLCV).
            **kwargs: پارامترهای اختیاری مخصوص هر اندیکاتور.
        """
        if not isinstance(df, pd.DataFrame) or df.empty:
            raise ValueError("Input must be a non-empty pandas DataFrame.")
        
        # ما یک کپی از df ذخیره می‌کنیم تا از تغییرات ناخواسته (Side Effects) جلوگیری کنیم.
        self.df = df
        # پارامترها در self.params ذخیره می‌شوند تا در سراسر کلاس قابل دسترس باشند.
        # این الگو به ما اجازه می‌دهد تا به راحتی پارامترها را از config بخوانیم.
        self.params = kwargs.get('params', kwargs)
        
        logger.debug(f"Initialized {self.__class__.__name__} with params: {self.params}")

    @abstractmethod
    def calculate(self) -> 'BaseIndicator':
        """
        متد انتزاعی برای محاسبه اندیکاتور.
        این متد باید توسط هر کلاس فرزند پیاده‌سازی شود و در نهایت `self` را برگرداند.
        """
        pass

    @abstractmethod
    def analyze(self) -> dict:
        """
        متد انتزاعی برای تحلیل نتیجه اندیکاتور.
        این متد باید آخرین وضعیت را تحلیل کرده و یک دیکشنری استاندارد برگرداند.
        """
        pass
