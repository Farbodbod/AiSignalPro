# engines/indicators/mfi.py

import pandas as pd
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class MfiIndicator(BaseIndicator):
    """
    کلاس محاسبه و تحلیل حرفه‌ای اندیکاتور Money Flow Index (MFI).

    MFI یک نوسانگر است که از داده‌های قیمت و حجم برای اندازه‌گیری فشار خرید و فروش
    استفاده می‌کند. این اندیکاتور به عنوان "RSI مبتنی بر حجم" شناخته می‌شود.
    """

    def __init__(self, df: pd.DataFrame, period: int = 14):
        """
        سازنده کلاس MFI.

        Args:
            df (pd.DataFrame): دیتافریم OHLCV.
            period (int): دوره زمانی برای محاسبه MFI.
        """
        super().__init__(df, period=period)
        self.period = period
        self.mfi_col = f'mfi_{period}'

    def calculate(self) -> pd.DataFrame:
        """
        مقدار MFI را بر اساس فرمول استاندارد آن محاسبه می‌کند.
        """
        # ۱. محاسبه قیمت نوعی (Typical Price)
        tp = (self.df['high'] + self.df['low'] + self.df['close']) / 3
        
        # ۲. محاسبه جریان پول خام (Raw Money Flow)
        raw_money_flow = tp * self.df['volume']
        
        # ۳. تعیین جریان پول مثبت و منفی
        # اگر قیمت نوعی امروز از دیروز بیشتر باشد، جریان مثبت است
        price_diff = tp.diff(1)
        positive_money_flow = raw_money_flow.where(price_diff > 0, 0)
        negative_money_flow = raw_money_flow.where(price_diff < 0, 0)

        # ۴. محاسبه مجموع جریان پول مثبت و منفی در دوره مشخص
        positive_mf_sum = positive_money_flow.rolling(window=self.period).sum()
        negative_mf_sum = negative_money_flow.rolling(window=self.period).sum()

        # ۵. محاسبه نسبت جریان پول (Money Flow Ratio)
        # افزودن 1e-12 برای جلوگیری از خطای تقسیم بر صفر
        money_ratio = positive_mf_sum / (negative_mf_sum + 1e-12)
        
        # ۶. محاسبه نهایی MFI
        self.df[self.mfi_col] = 100 - (100 / (1 + money_ratio))

        logger.debug("Calculated MFI successfully.")
        return self.df

    def analyze(self) -> dict:
        """
        آخرین وضعیت MFI را تحلیل کرده و وضعیت اشباع خرید/فروش را مشخص می‌کند.
        این تحلیل به دلیل مبتنی بودن بر حجم، اعتبار بالایی دارد.
        """
        required_cols = [self.mfi_col]
        if not all(col in self.df.columns and not self.df[col].isnull().all() for col in required_cols):
            raise ValueError("MFI column not found or is all NaN. Please run calculate() first.")

        last_mfi = self.df[self.mfi_col].iloc[-1]
        
        signal = "Neutral"
        if last_mfi > 80:
            signal = "Overbought (High Volume)"
        elif last_mfi < 20:
            signal = "Oversold (High Volume)"
            
        return {
            "value": round(last_mfi, 2),
            "signal": signal
        }
