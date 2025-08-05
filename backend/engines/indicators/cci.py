# engines/indicators/cci.py

import pandas as pd
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class CciIndicator(BaseIndicator):
    """
    کلاس محاسبه و تحلیل حرفه‌ای اندیکاتور Commodity Channel Index (CCI).

    CCI یک نوسانگر است که برای شناسایی شروع یک روند جدید یا شرایط بازگشتی افراطی
    (Extreme Reversal Conditions) استفاده می‌شود. این اندیکاتور، انحراف قیمت فعلی
    از میانگین آماری آن را اندازه‌گیری می‌کند.
    """

    def __init__(self, df: pd.DataFrame, period: int = 20, constant: float = 0.015):
        """
        سازنده کلاس CCI.

        Args:
            df (pd.DataFrame): دیتافریم OHLCV.
            period (int): دوره زمانی برای محاسبه CCI.
            constant (float): ثابت استاندارد در فرمول CCI.
        """
        super().__init__(df, period=period, constant=constant)
        self.period = period
        self.constant = constant
        self.cci_col = f'cci_{period}'

    def calculate(self) -> pd.DataFrame:
        """
        مقدار CCI را بر اساس فرمول استاندارد آن محاسبه می‌کند.
        """
        # ۱. محاسبه قیمت نوعی (Typical Price)
        tp = (self.df['high'] + self.df['low'] + self.df['close']) / 3
        
        # ۲. محاسبه میانگین متحرک ساده از قیمت نوعی
        ma_tp = tp.rolling(window=self.period).mean()
        
        # ۳. محاسبه میانگین انحراف (Mean Deviation)
        # این بخش کلیدی‌ترین تفاوت CCI با سایر نوسانگرهاست
        mean_dev = tp.rolling(window=self.period).apply(lambda x: (x - x.mean()).abs().mean(), raw=True)
        
        # ۴. محاسبه نهایی CCI
        # افزودن مقدار کوچک 1e-12 برای جلوگیری از خطای تقسیم بر صفر
        self.df[self.cci_col] = (tp - ma_tp) / (self.constant * mean_dev + 1e-12)

        logger.debug("Calculated CCI successfully.")
        return self.df

    def analyze(self) -> dict:
        """
        آخرین وضعیت CCI را تحلیل کرده و سیگنال‌های مربوط به عبور از سطوح
        کلیدی +100 و -100 را شناسایی می‌کند.
        """
        required_cols = [self.cci_col]
        if not all(col in self.df.columns and not self.df[col].isnull().all() for col in required_cols):
            raise ValueError("CCI column not found or is all NaN. Please run calculate() first.")

        last_row = self.df.iloc[-1]
        prev_row = self.df.iloc[-2]
        
        cci_val = last_row[self.cci_col]
        prev_cci_val = prev_row[self.cci_col]

        # تعیین وضعیت کلی
        position = "Neutral Zone"
        if cci_val > 100:
            position = "Overbought / Strong Uptrend"
        elif cci_val < -100:
            position = "Oversold / Strong Downtrend"
        
        signal = "Neutral"
        # تشخیص عبور از خطوط سیگنال
        # عبور به بالای ۱۰۰+ می‌تواند نشانه شروع یک روند صعودی قوی باشد
        if prev_cci_val < 100 and cci_val > 100:
            signal = "Bullish Threshold Cross"
        # عبور به زیر ۱۰۰- می‌تواند نشانه شروع یک روند نزولی قوی باشد
        elif prev_cci_val > -100 and cci_val < -100:
            signal = "Bearish Threshold Cross"
        # بازگشت به داخل محدوده از بالا، می‌تواند سیگنال فروش باشد
        elif prev_cci_val > 100 and cci_val < 100:
            signal = "Potential Sell Signal (Re-entry)"
        # بازگشت به داخل محدوده از پایین، می‌تواند سیگنال خرید باشد
        elif prev_cci_val < -100 and cci_val > -100:
            signal = "Potential Buy Signal (Re-entry)"

        return {
            "value": round(cci_val, 2),
            "position": position,
            "signal": signal
        }
