# engines/indicators/adx.py

import pandas as pd
import numpy as np
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class AdxIndicator(BaseIndicator):
    """
    کلاس محاسبه و تحلیل حرفه‌ای اندیکاتور Average Directional Index (ADX).

    این ماژول برای اندازه‌گیری قدرت یک روند (و نه جهت آن) طراحی شده است.
    - ADX: خط اصلی قدرت روند.
    - +DI: نشان‌دهنده قدرت حرکت صعودی.
    - -DI: نشان‌دهنده قدرت حرکت نزولی.
    """

    def __init__(self, df: pd.DataFrame, period: int = 14):
        """
        سازنده کلاس ADX.

        Args:
            df (pd.DataFrame): دیتافریم OHLCV.
            period (int): دوره زمانی برای محاسبه ADX و DI (پیش‌فرض ۱۴).
        """
        super().__init__(df, period=period)
        self.period = period
        self.adx_col = f'adx_{period}'
        self.plus_di_col = f'plus_di_{period}'
        self.minus_di_col = f'minus_di_{period}'

    def calculate(self) -> pd.DataFrame:
        """
        محاسبه کامل خطوط ADX, +DI و -DI با استفاده از روش استاندارد Wilder's Smoothing.
        """
        df = self.df.copy() # کار بر روی یک کپی برای جلوگیری از خطاهای زنجیره‌ای

        # ۱. محاسبه True Range (TR)
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift(1))
        low_close = np.abs(df['low'] - df['close'].shift(1))
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        # استفاده از ewm برای Wilder's Smoothing
        atr = tr.ewm(alpha=1/self.period, adjust=False).mean()

        # ۲. محاسبه حرکات جهت‌دار (+DM و -DM)
        move_up = df['high'].diff()
        move_down = df['low'].diff()
        plus_dm = np.where((move_up > move_down) & (move_up > 0), move_up, 0.0)
        minus_dm = np.where((move_down > move_up) & (move_down > 0), move_down, 0.0)
        
        # اعمال Wilder's Smoothing
        plus_dm_smooth = pd.Series(plus_dm).ewm(alpha=1/self.period, adjust=False).mean()
        minus_dm_smooth = pd.Series(minus_dm).ewm(alpha=1/self.period, adjust=False).mean()

        # ۳. محاسبه +DI و -DI
        self.df[self.plus_di_col] = (plus_dm_smooth / (atr + 1e-12)) * 100
        self.df[self.minus_di_col] = (minus_dm_smooth / (atr + 1e-12)) * 100

        # ۴. محاسبه ADX
        dx = (np.abs(self.df[self.plus_di_col] - self.df[self.minus_di_col]) / (self.df[self.plus_di_col] + self.df[self.minus_di_col] + 1e-12)) * 100
        # اعمال Wilder's Smoothing نهایی برای ADX
        self.df[self.adx_col] = dx.ewm(alpha=1/self.period, adjust=False).mean()

        logger.debug("Calculated ADX, +DI, and -DI successfully.")
        return self.df

    def analyze(self) -> dict:
        """
        آخرین وضعیت ADX را تحلیل کرده و قدرت و جهت روند را مشخص می‌کند.
        """
        required_cols = [self.adx_col, self.plus_di_col, self.minus_di_col]
        if not all(col in self.df.columns and not self.df[col].isnull().all() for col in required_cols):
            raise ValueError("ADX columns not found or are all NaN. Please run calculate() first.")

        last_row = self.df.iloc[-1]
        
        adx_value = last_row[self.adx_col]
        plus_di = last_row[self.plus_di_col]
        minus_di = last_row[self.minus_di_col]

        # تحلیل قدرت روند بر اساس مقدار ADX
        trend_strength = "No Trend"
        if 20 < adx_value <= 25:
            trend_strength = "Weak Trend"
        elif 25 < adx_value <= 50:
            trend_strength = "Strong Trend"
        elif adx_value > 50:
            trend_strength = "Very Strong Trend"

        # تحلیل جهت روند بر اساس مقایسه +DI و -DI
        trend_direction = "Neutral"
        if plus_di > minus_di:
            trend_direction = "Bullish"
        elif minus_di > plus_di:
            trend_direction = "Bearish"

        # ترکیب تحلیل‌ها برای یک سیگنال نهایی
        signal = f"{trend_strength} ({trend_direction})"

        return {
            "adx": round(adx_value, 2),
            "plus_di": round(plus_di, 2),
            "minus_di": round(minus_di, 2),
            "strength": trend_strength,
            "direction": trend_direction,
            "signal": signal
        }
