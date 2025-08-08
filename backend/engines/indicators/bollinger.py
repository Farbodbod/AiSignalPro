import pandas as pd
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class BollingerIndicator(BaseIndicator):
    """
    ✨ UPGRADE v2.1 - JSON Serializable ✨
    کلاس محاسبه و تحلیل حرفه‌ای اندیکاتور Bollinger Bands.
    خروجی‌ها برای سازگاری کامل با JSON استانداردسازی شده‌اند.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.period = self.params.get('period', 20)
        self.std_dev = self.params.get('std_dev', 2)
        self.middle_col = f'bb_middle_{self.period}'
        self.upper_col = f'bb_upper_{self.period}'
        self.lower_col = f'bb_lower_{self.period}'
        self.width_col = f'bb_width_{self.period}'
        self.percent_b_col = f'bb_percent_b_{self.period}'

    def calculate(self) -> pd.DataFrame:
        """
        هر پنج مولفه بولینگر بندز را محاسبه کرده و به دیتافریم اضافه می‌کند.
        """
        self.df[self.middle_col] = self.df['close'].rolling(window=self.period).mean()
        std = self.df['close'].rolling(window=self.period).std()
        self.df[self.upper_col] = self.df[self.middle_col] + (std * self.std_dev)
        self.df[self.lower_col] = self.df[self.middle_col] - (std * self.std_dev)
        self.df[self.width_col] = ((self.df[self.upper_col] - self.df[self.lower_col]) / (self.df[self.middle_col] + 1e-12)) * 100
        self.df[self.percent_b_col] = (self.df['close'] - self.df[self.lower_col]) / (self.df[self.upper_col] - self.df[self.lower_col] + 1e-12)
        return self.df

    def analyze(self) -> dict:
        """
        آخرین وضعیت بولینگر بندز را تحلیل کرده و سیگنال‌های کلیدی را استخراج می‌کند.
        """
        last_row = self.df.iloc[-1]
        
        lowest_width_in_lookback = self.df[self.width_col].rolling(window=120, min_periods=1).min().iloc[-1]
        # ✨ اصلاحیه کلیدی: تبدیل نوع داده NumPy به bool استاندارد پایتون
        is_squeeze = bool(last_row[self.width_col] <= (lowest_width_in_lookback * 1.1)) if pd.notna(lowest_width_in_lookback) else False
        
        position = "Inside Bands"
        if last_row[self.percent_b_col] > 1.0:
            position = "Breakout Above Upper Band"
        elif last_row[self.percent_b_col] < 0.0:
            position = "Breakdown Below Lower Band"
        
        signal = position
        if is_squeeze:
            signal = "Volatility Squeeze"

        return {
            "upper_band": round(last_row[self.upper_col], 5),
            "middle_band": round(last_row[self.middle_col], 5),
            "lower_band": round(last_row[self.lower_col], 5),
            "bandwidth": round(last_row[self.width_col], 4),
            "percent_b": round(last_row[self.percent_b_col], 3),
            "is_squeeze": is_squeeze,
            "position": position,
            "signal": signal
        }
