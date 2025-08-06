# engines/indicators/pattern_indicator.py (نسخه نهایی با قابلیت سکوت هشدار)
import pandas as pd
import pandas_ta as ta
import logging
import warnings # <-- ایمپورت جدید
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class PatternIndicator(BaseIndicator):
    """
    این ماژول، الگوهای شمعی را با استفاده از کتابخانه مدرن pandas-ta شناسایی می‌کند.
    این نسخه شامل منطقی برای جلوگیری از چاپ هشدارهای اضافی در لاگ است.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.pattern_col = 'identified_pattern'

    def calculate(self) -> pd.DataFrame:
        """
        از قابلیت شناسایی الگوی pandas-ta برای یافتن تمام الگوهای موجود استفاده می‌کند.
        """
        try:
            # --- ✨ تغییر کلیدی: ساکت کردن موقت هشدارها ---
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                # اجرای متد .cdl_pattern() از pandas-ta در این محیط امن
                patterns_df = self.df.ta.cdl_pattern(name="all")
            # --- پایان تغییر کلیدی ---

            last_candle_patterns = patterns_df.iloc[-1]
            found_patterns = last_candle_patterns[last_candle_patterns != 0]

            if not found_patterns.empty:
                pattern_names = [col.replace('CDL_', '') for col in found_patterns.index]
                self.df.loc[self.df.index[-1], self.pattern_col] = ", ".join(pattern_names)
            else:
                self.df.loc[self.df.index[-1], self.pattern_col] = "None"
        except Exception as e:
            logger.error(f"Error calculating candlestick patterns with pandas-ta: {e}")
            self.df[self.pattern_col] = "None"
        return self.df

    def analyze(self) -> dict:
        """
        نام الگوی(های) شناسایی شده در آخرین کندل را به صورت یک لیست برمی‌گرداند.
        """
        last_patterns_str = self.df.iloc[-1].get(self.pattern_col, "None")
        if last_patterns_str == "None" or pd.isna(last_patterns_str):
            return {"patterns": []}
        return {"patterns": [p.strip() for p in last_patterns_str.split(',')]}

