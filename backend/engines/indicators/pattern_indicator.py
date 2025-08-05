# engines/indicators/pattern_indicator.py (نسخه جدید با pandas-ta)

import pandas as pd
import pandas_ta as ta
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class PatternIndicator(BaseIndicator):
    """
    این ماژول، الگوهای شمعی را با استفاده از کتابخانه مدرن و قدرتمند pandas-ta
    شناسایی می‌کند. این کتابخانه به کامپایلر خارجی نیازی ندارد.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.pattern_col = 'identified_pattern'

    def calculate(self) -> pd.DataFrame:
        """
        از قابلیت شناسایی الگوی pandas-ta برای یافتن تمام الگوهای موجود استفاده می‌کند.
        """
        # اجرای متد .cdl_pattern() از pandas-ta روی دیتافریم
        # این متد تمام الگوهای کندلی را بررسی کرده و نام الگوی پیدا شده را برمی‌گرداند
        try:
            patterns_df = self.df.ta.cdl_pattern(name="all")
            # ما فقط به ستون‌هایی نیاز داریم که حداقل یک الگو را در کندل آخر شناسایی کرده باشند
            # مقادیر غیر صفر نشان دهنده وجود الگو هستند
            last_candle_patterns = patterns_df.iloc[-1]
            found_patterns = last_candle_patterns[last_candle_patterns != 0]

            if not found_patterns.empty:
                # نام الگوها را استخراج کرده و با کاما به هم متصل می‌کنیم
                # مثال نام ستون: 'CDL_ENGULFING'
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

