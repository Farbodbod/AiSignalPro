import pandas as pd
import numpy as np
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class DonchianChannelIndicator(BaseIndicator):
    """
    پیاده‌سازی اندیکاتور Donchian Channel برای شناسایی شکست‌های قیمتی (breakouts).
    """

    def calculate(self) -> pd.DataFrame:
        """
        محاسبه باندهای بالا، پایین و میانی کانال دونچیان.

        Returns:
            pd.DataFrame: دیتافریم به‌روز شده با ستون‌های کانال.
        """
        self.period = self.params.get('period', 20)
        logger.debug(f"Calculating Donchian Channel with period={self.period}")

        # --- محاسبه باندها با استفاده از rolling window ---
        self.upper_col = f'donchian_upper_{self.period}'
        self.lower_col = f'donchian_lower_{self.period}'
        self.middle_col = f'donchian_middle_{self.period}'

        self.df[self.upper_col] = self.df['high'].rolling(window=self.period).max()
        self.df[self.lower_col] = self.df['low'].rolling(window=self.period).min()
        self.df[self.middle_col] = (self.df[self.upper_col] + self.df[self.lower_col]) / 2
        
        return self.df

    def analyze(self) -> dict:
        """
        تحلیل موقعیت قیمت نسبت به کانال برای شناسایی سیگنال‌های شکست.
        از منطق "شکست تایید شده" (Confirmed Breakout) استفاده می‌شود.

        Returns:
            dict: یک دیکشنری حاوی تحلیل نهایی.
        """
        # برای تحلیل شکست، به دو کندل آخر نیاز داریم
        if len(self.df) < 2:
            return {'signal': 'neutral', 'message': 'Not enough data for analysis.'}
            
        last_row = self.df.iloc[-1]
        prev_row = self.df.iloc[-2]
        
        close_price = last_row['close']
        
        analysis = {
            'indicator': self.__class__.__name__,
            'params': {'period': self.period},
            'values': {
                'close': close_price,
                'upper_band': round(last_row[self.upper_col], 4),
                'middle_band': round(last_row[self.middle_col], 4),
                'lower_band': round(last_row[self.lower_col], 4)
            }
        }

        # سیگنال خرید: قیمت بسته شدن فعلی > باند بالای قبلی
        if close_price > prev_row[self.upper_col]:
            analysis['signal'] = 'buy'
            analysis['message'] = f"Confirmed Breakout: Price closed above the previous upper Donchian band."
        # سیگنال فروش: قیمت بسته شدن فعلی < باند پایین قبلی
        elif close_price < prev_row[self.lower_col]:
            analysis['signal'] = 'sell'
            analysis['message'] = f"Confirmed Breakdown: Price closed below the previous lower Donchian band."
        else:
            analysis['signal'] = 'neutral'
            analysis['message'] = "Price is moving inside the Donchian Channel."
            
        return analysis
