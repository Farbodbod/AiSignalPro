import pandas as pd
import numpy as np
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class VwapBandsIndicator(BaseIndicator):
    """
    پیاده‌سازی اندیکاتور VWAP (Volume-Weighted Average Price) با باندهای انحراف معیار.
    این اندیکاتور به صورت روزانه ریست می‌شود که برای معاملات روزانه حیاتی است.
    """

    def calculate(self) -> pd.DataFrame:
        """
        محاسبه VWAP و باندهای بالا و پایین آن.
        این متد باید روی دیتافریمی اجرا شود که ایندکس آن از نوع Datetime باشد.

        Returns:
            pd.DataFrame: دیتافریم به‌روز شده با ستون‌های VWAP و باندهای آن.
        """
        self.std_dev_multiplier = self.params.get('std_dev_multiplier', 1.0)
        
        # اطمینان از اینکه ایندکس از نوع datetime است
        if not isinstance(self.df.index, pd.DatetimeIndex):
            raise TypeError("DataFrame index must be a DatetimeIndex for VWAP calculation.")

        logger.debug(f"Calculating VWAP Bands with std_dev_multiplier={self.std_dev_multiplier}")

        # --- محاسبات اصلی VWAP ---
        # قیمت معمول (Typical Price)
        tp = (self.df['high'] + self.df['low'] + self.df['close']) / 3
        tp_volume = tp * self.df['volume']

        # گروه‌بندی بر اساس روز (مهم‌ترین بخش برای ریست شدن روزانه)
        # cumsum() روی هر گروه (روز) به صورت جداگانه اعمال می‌شود
        daily_grouper = self.df.index.to_series().dt.date
        
        cumulative_volume = self.df['volume'].groupby(daily_grouper).cumsum()
        cumulative_tp_volume = tp_volume.groupby(daily_grouper).cumsum()

        # محاسبه خط اصلی VWAP
        self.df['vwap'] = cumulative_tp_volume / cumulative_volume

        # --- محاسبه باندهای انحراف معیار ---
        # فرمول واریانس وزنی-حجمی
        squared_diff = ((tp - self.df['vwap'])**2) * self.df['volume']
        cumulative_squared_diff = squared_diff.groupby(daily_grouper).cumsum()
        
        # واریانس روزانه
        daily_variance = cumulative_squared_diff / cumulative_volume
        
        # انحراف معیار روزانه
        daily_std_dev = np.sqrt(daily_variance)

        # محاسبه باندها
        self.df['upper_band'] = self.df['vwap'] + (daily_std_dev * self.std_dev_multiplier)
        self.df['lower_band'] = self.df['vwap'] - (daily_std_dev * self.std_dev_multiplier)
        
        self.df.fillna(0, inplace=True) # پر کردن مقادیر NaN اولیه

        return self.df

    def analyze(self) -> dict:
        """
        تحلیل آخرین موقعیت قیمت نسبت به باندهای VWAP.

        Returns:
            dict: یک دیکشنری حاوی تحلیل نهایی.
        """
        last_row = self.df.iloc[-1]
        close_price = last_row['close']
        
        analysis = {
            'indicator': self.__class__.__name__,
            'params': {'std_dev_multiplier': self.std_dev_multiplier},
            'values': {
                'close': close_price,
                'vwap': round(last_row['vwap'], 4),
                'upper_band': round(last_row['upper_band'], 4),
                'lower_band': round(last_row['lower_band'], 4)
            }
        }

        if close_price > last_row['upper_band']:
            analysis['signal'] = 'sell'
            analysis['message'] = "Price is above the upper VWAP band (Overbought)."
        elif close_price < last_row['lower_band']:
            analysis['signal'] = 'buy'
            analysis['message'] = "Price is below the lower VWAP band (Oversold)."
        else:
            analysis['signal'] = 'neutral'
            analysis['message'] = "Price is within the VWAP bands."
            
        return analysis

