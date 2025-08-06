# engines/indicators/cci.py (نسخه نهایی با اصلاحیه باگ numpy.abs)

import pandas as pd
import numpy as np  # <--- ۱. ایمپورت کردن numpy
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class CciIndicator(BaseIndicator):
    """
    کلاس محاسبه و تحلیل حرفه‌ای اندیکاتور Commodity Channel Index (CCI).
    """

    def __init__(self, df: pd.DataFrame, period: int = 20, constant: float = 0.015):
        super().__init__(df, period=period, constant=constant)
        self.period = period
        self.constant = constant
        self.cci_col = f'cci_{period}'

    def calculate(self) -> pd.DataFrame:
        """
        مقدار CCI را بر اساس فرمول استاندارد آن محاسبه می‌کند.
        """
        tp = (self.df['high'] + self.df['low'] + self.df['close']) / 3
        ma_tp = tp.rolling(window=self.period).mean()
        
        # --- ✨ ۲. اصلاحیه کلیدی باگ ---
        # استفاده از np.abs() به جای .abs() برای سازگاری کامل با numpy
        mean_dev = tp.rolling(window=self.period).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
        
        self.df[self.cci_col] = (tp - ma_tp) / (self.constant * mean_dev + 1e-12)

        logger.debug("Calculated CCI successfully.")
        return self.df

    def analyze(self) -> dict:
        """
        آخرین وضعیت CCI را تحلیل کرده و سیگنال‌های مربوط به عبور از سطوح
        کلیدی +100 و -100 را شناسایی می‌کند.
        """
        # ... (این متد بدون تغییر و صحیح است) ...
        required_cols = [self.cci_col]
        if not all(col in self.df.columns and not self.df[col].isnull().all() for col in required_cols):
            raise ValueError("CCI column not found or are all NaN. Please run calculate() first.")

        last_row = self.df.iloc[-1]
        prev_row = self.df.iloc[-2]
        
        cci_val = last_row[self.cci_col]
        prev_cci_val = prev_row[self.cci_col]

        position = "Neutral Zone"
        if cci_val > 100:
            position = "Overbought / Strong Uptrend"
        elif cci_val < -100:
            position = "Oversold / Strong Downtrend"
        
        signal = "Neutral"
        if prev_cci_val < 100 and cci_val > 100:
            signal = "Bullish Threshold Cross"
        elif prev_cci_val > -100 and cci_val < -100:
            signal = "Bearish Threshold Cross"
        elif prev_cci_val > 100 and cci_val < 100:
            signal = "Potential Sell Signal (Re-entry)"
        elif prev_cci_val < -100 and cci_val > -100:
            signal = "Potential Buy Signal (Re-entry)"

        return {
            "value": round(cci_val, 2),
            "position": position,
            "signal": signal
        }
