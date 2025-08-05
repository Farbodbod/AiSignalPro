# engines/indicators/supertrend.py

import pandas as pd
import numpy as np
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class SuperTrendIndicator(BaseIndicator):
    """
    کلاس محاسبه و تحلیل حرفه‌ای اندیکاتور SuperTrend.

    این اندیکاتور برای شناسایی روند اصلی بازار و ارائه سطوح حد ضرر متحرک استفاده می‌شود.
    ویژگی کلیدی این پیاده‌سازی، تشخیص دقیق لحظه "تغییر روند" است.
    """

    def __init__(self, df: pd.DataFrame, period: int = 10, multiplier: float = 3.0):
        """
        سازنده کلاس SuperTrend.

        Args:
            df (pd.DataFrame): دیتافریم OHLCV.
            period (int): دوره زمانی برای محاسبه ATR.
            multiplier (float): ضریبی که برای فاصله گرفتن از قیمت استفاده می‌شود.
        """
        super().__init__(df, period=period, multiplier=multiplier)
        self.period = period
        self.multiplier = multiplier
        self.supertrend_col = f'supertrend_{period}_{multiplier}'
        self.direction_col = f'supertrend_dir_{period}_{multiplier}'

    def _calculate_atr(self, df: pd.DataFrame) -> pd.Series:
        """یک متد داخلی و خصوصی برای محاسبه ATR."""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift(1))
        low_close = np.abs(df['low'] - df['close'].shift(1))
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        # استفاده از ewm برای Wilder's Smoothing که برای ATR استاندارد است
        return tr.ewm(alpha=1/self.period, adjust=False).mean()

    def calculate(self) -> pd.DataFrame:
        """
        محاسبه خط SuperTrend و جهت آن.
        نکته مهم: محاسبه SuperTrend به ذات خود یک فرآیند تکراری (iterative) است
        و نمی‌توان آن را به سادگی با توابع برداری pandas انجام داد، زیرا هر مقدار
        به مقدار محاسبه‌شده قبلی خود وابسته است. به همین دلیل از یک حلقه استفاده می‌کنیم.
        """
        df = self.df.copy()
        
        # ۱. محاسبه ATR به عنوان پیش‌نیاز
        atr = self._calculate_atr(df)
        
        # ۲. محاسبه باندهای پایه بالا و پایین
        basic_upperband = (df['high'] + df['low']) / 2 + self.multiplier * atr
        basic_lowerband = (df['high'] + df['low']) / 2 - self.multiplier * atr

        # ۳. آماده‌سازی ستون‌های نهایی در دیتافریم
        supertrend = pd.Series(np.nan, index=df.index)
        direction = pd.Series(np.nan, index=df.index)

        # ۴. حلقه اصلی برای محاسبه تکراری
        for i in range(self.period, len(df)):
            # اگر قیمت کندل قبلی از خط سوپرترند قبلی بالاتر باشد (روند صعودی)
            if df['close'][i-1] > supertrend[i-1]:
                # خط سوپرترند فعلی، بزرگترین مقدار بین باند پایین فعلی و سوپرترند قبلی است
                supertrend[i] = max(basic_lowerband[i], supertrend[i-1])
            else: # روند نزولی
                # خط سوپرترند فعلی، کوچکترین مقدار بین باند بالای فعلی و سوپرترند قبلی است
                supertrend[i] = min(basic_upperband[i], supertrend[i-1])

            # تعیین جهت نهایی
            if df['close'][i] > supertrend[i]:
                direction[i] = 1  # روند صعودی
            else:
                direction[i] = -1 # روند نزولی
        
        self.df[self.supertrend_col] = supertrend
        self.df[self.direction_col] = direction
        
        logger.debug("Calculated SuperTrend line and direction successfully.")
        return self.df

    def analyze(self) -> dict:
        """
        آخرین وضعیت SuperTrend را تحلیل کرده و لحظه تغییر روند را شکار می‌کند.
        """
        required_cols = [self.supertrend_col, self.direction_col]
        if not all(col in self.df.columns and not self.df[col].isnull().all() for col in required_cols):
            raise ValueError("SuperTrend columns not found or are all NaN. Please run calculate() first.")
        
        # استخراج دو ردیف آخر برای تشخیص تغییر جهت
        last_row = self.df.iloc[-1]
        prev_row = self.df.iloc[-2]

        last_direction = last_row[self.direction_col]
        prev_direction = prev_row[self.direction_col]

        trend = "Uptrend" if last_direction == 1 else "Downtrend"
        signal = "Trend Continuation"

        # تشخیص دقیق لحظه تغییر روند
        if last_direction == 1 and prev_direction == -1:
            signal = "Bullish Trend Change"
        elif last_direction == -1 and prev_direction == 1:
            signal = "Bearish Trend Change"
            
        return {
            "value": round(last_row[self.supertrend_col], 5),
            "trend": trend,
            "signal": signal
        }
