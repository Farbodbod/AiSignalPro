import pandas as pd
import numpy as np
import logging
from .base import BaseIndicator
from .atr import AtrIndicator # استفاده مجدد از کد برای اصل DRY

logger = logging.getLogger(__name__)

class KeltnerChannelIndicator(BaseIndicator):
    """
    پیاده‌سازی اندیکاتور Keltner Channel، یک کانال نوسان مبتنی بر EMA و ATR.
    """

    def calculate(self) -> pd.DataFrame:
        """
        محاسبه خطوط میانی، بالایی و پایینی کانال کلتنر.

        Returns:
            pd.DataFrame: دیتافریم به‌روز شده با ستون‌های کانال.
        """
        self.ema_period = self.params.get('ema_period', 20)
        self.atr_period = self.params.get('atr_period', 10)
        self.atr_multiplier = self.params.get('atr_multiplier', 2.0)

        logger.debug(f"Calculating Keltner Channel with ema_period={self.ema_period}, atr_period={self.atr_period}, multiplier={self.atr_multiplier}")

        # --- محاسبه خط میانی (EMA) ---
        self.middle_col = f'keltner_middle_{self.ema_period}'
        self.df[self.middle_col] = self.df['close'].ewm(span=self.ema_period, adjust=False).mean()

        # --- محاسبه ATR با استفاده از کلاس موجود ---
        atr_indicator = AtrIndicator(df=self.df, period=self.atr_period)
        self.df = atr_indicator.calculate()
        atr_col_name = f'atr_{self.atr_period}'
        
        atr_value = self.df[atr_col_name] * self.atr_multiplier

        # --- محاسبه باندهای بالا و پایین ---
        self.upper_col = f'keltner_upper_{self.ema_period}_{self.atr_multiplier}'
        self.lower_col = f'keltner_lower_{self.ema_period}_{self.atr_multiplier}'

        self.df[self.upper_col] = self.df[self.middle_col] + atr_value
        self.df[self.lower_col] = self.df[self.middle_col] - atr_value
        
        return self.df

    def analyze(self) -> dict:
        """
        تحلیل موقعیت قیمت نسبت به کانال برای شناسایی سیگنال‌های شکست.

        Returns:
            dict: یک دیکشنری حاوی تحلیل نهایی.
        """
        last_row = self.df.iloc[-1]
        close_price = last_row['close']
        upper_band = last_row[self.upper_col]
        lower_band = last_row[self.lower_col]

        analysis = {
            'indicator': self.__class__.__name__,
            'params': {'ema_p': self.ema_period, 'atr_p': self.atr_period, 'atr_m': self.atr_multiplier},
            'values': {
                'close': close_price,
                'upper_band': round(upper_band, 4),
                'middle_band': round(last_row[self.middle_col], 4),
                'lower_band': round(lower_band, 4)
            }
        }

        if close_price > upper_band:
            analysis['signal'] = 'buy'
            analysis['message'] = "Price closed strongly above the upper Keltner Channel band. Strong bullish breakout."
        elif close_price < lower_band:
            analysis['signal'] = 'sell'
            analysis['message'] = "Price closed strongly below the lower Keltner Channel band. Strong bearish breakdown."
        else:
            analysis['signal'] = 'neutral'
            analysis['message'] = "Price is contained within the Keltner Channel."
            
        return analysis

