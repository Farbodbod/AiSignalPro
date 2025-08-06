import pandas as pd
import numpy as np
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class ZigzagIndicator(BaseIndicator):
    """
    پیاده‌سازی اندیکاتور ZigZag هوشمند، غیر-بازترسیم شونده و پایدار.
    این اندیکاتور پیوت‌های ماژور بازار را که تثبیت شده‌اند، شناسایی می‌کند.
    """

    def _get_pivots(self, deviation_threshold: float):
        """
        الگوریتم اصلی برای یافتن نقاط پیوت تثبیت شده.
        این یک الگوریتم stateful است و به صورت 순차ی عمل می‌کند.
        """
        pivots = np.zeros(len(self.df), dtype=int)
        prices = np.zeros(len(self.df), dtype=float)
        
        last_pivot_price = 0
        last_pivot_idx = 0
        trend = 0  # 1 for uptrend, -1 for downtrend

        # اولین کندل را به عنوان نقطه شروع در نظر می‌گیریم
        last_pivot_price = self.df['close'].iloc[0]
        
        # شناسایی اکسترمم‌های محلی برای شروع بهتر
        highs = self.df['high']
        lows = self.df['low']

        for i in range(1, len(self.df)):
            current_high = highs.iloc[i]
            current_low = lows.iloc[i]

            if trend == 0:  # تعیین روند اولیه
                if current_high > last_pivot_price * (1 + deviation_threshold / 100):
                    trend = 1 # روند صعودی شد
                    last_pivot_price = current_high
                    last_pivot_idx = i
                elif current_low < last_pivot_price * (1 - deviation_threshold / 100):
                    trend = -1 # روند نزولی شد
                    last_pivot_price = current_low
                    last_pivot_idx = i
            
            elif trend == 1: # در یک روند صعودی هستیم
                if current_high > last_pivot_price:
                    # سقف جدیدتر پیدا شد، آپدیت می‌کنیم
                    last_pivot_price = current_high
                    last_pivot_idx = i
                elif current_low < last_pivot_price * (1 - deviation_threshold / 100):
                    # قیمت به اندازه کافی از سقف آخر پایین آمده -> سقف قبلی تثبیت شد
                    pivots[last_pivot_idx] = 1 # 1 for peak
                    prices[last_pivot_idx] = last_pivot_price
                    trend = -1 # روند به نزولی تغییر کرد
                    last_pivot_price = current_low
                    last_pivot_idx = i

            elif trend == -1: # در یک روند نزولی هستیم
                if current_low < last_pivot_price:
                    # کف جدیدتر پیدا شد، آپدیت می‌کنیم
                    last_pivot_price = current_low
                    last_pivot_idx = i
                elif current_high > last_pivot_price * (1 + deviation_threshold / 100):
                    # قیمت به اندازه کافی از کف آخر بالا رفته -> کف قبلی تثبیت شد
                    pivots[last_pivot_idx] = -1 # -1 for trough
                    prices[last_pivot_idx] = last_pivot_price
                    trend = 1 # روند به صعودی تغییر کرد
                    last_pivot_price = current_high
                    last_pivot_idx = i
        
        return pivots, prices

    def calculate(self) -> pd.DataFrame:
        """
        محاسبه نقاط پیوت ZigZag و افزودن آن‌ها به دیتافریم.
        """
        self.deviation_threshold = self.params.get('deviation', 5.0) # انحراف 5% به صورت پیش‌فرض
        logger.debug(f"Calculating ZigZag with deviation_threshold={self.deviation_threshold}%")

        self.col_name_pivots = f'zigzag_pivots_{self.deviation_threshold}'
        self.col_name_prices = f'zigzag_prices_{self.deviation_threshold}'

        pivots, prices = self._get_pivots(self.deviation_threshold)
        
        self.df[self.col_name_pivots] = pivots
        self.df[self.col_name_prices] = prices

        return self.df

    def analyze(self) -> dict:
        """
        تحلیل آخرین پیوت تثبیت شده برای تعیین روند فعلی بازار.
        """
        # پیدا کردن آخرین پیوت غیر صفر
        last_pivots = self.df[self.df[self.col_name_pivots] != 0]
        
        analysis = {
            'indicator': self.__class__.__name__,
            'params': {'deviation': self.deviation_threshold}
        }

        if last_pivots.empty:
            analysis['signal'] = 'neutral'
            analysis['message'] = "No confirmed ZigZag pivots found yet."
            return analysis

        last_pivot_row = last_pivots.iloc[-1]
        last_pivot_type = int(last_pivot_row[self.col_name_pivots])
        last_pivot_price = last_pivot_row[self.col_name_prices]
        last_pivot_time = last_pivot_row.name

        analysis['values'] = {
            'last_pivot_type': 'peak' if last_pivot_type == 1 else 'trough',
            'last_pivot_price': round(last_pivot_price, 4),
            'last_pivot_time': last_pivot_time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        if last_pivot_type == 1: # آخرین پیوت یک سقف بوده
            analysis['signal'] = 'sell'
            analysis['message'] = "Last confirmed pivot was a Peak. Current trend is considered Down."
        elif last_pivot_type == -1: # آخرین پیوت یک کف بوده
            analysis['signal'] = 'buy'
            analysis['message'] = "Last confirmed pivot was a Trough. Current trend is considered Up."
        
        return analysis
