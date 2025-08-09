from abc import ABC, abstractmethod
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class BaseIndicator(ABC):
    """
    کلاس پایه انتزاعی (Abstract Base Class) برای تمام اندیکاتورهای AiSignalPro (v2.0 - Final).
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
        
        # ما یک کپی از df را در ابتدا ذخیره نمی‌کنیم تا به اندیکاتور اجازه دهیم آن را تغییر دهد
        # و در نهایت نسخه تغییر یافته را برگرداند.
        self.df = df
        
        # این الگو به ما اجازه می‌دهد پارامترها را هم به صورت مستقیم و هم داخل یک دیکشنری 'params' ارسال کنیم.
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
        این متد باید به گونه‌ای طراحی شود که از سوگیری نگاه به آینده (Look-ahead Bias) جلوگیری کند.
        """
        pass
