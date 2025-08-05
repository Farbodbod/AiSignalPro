# engines/indicators/whale_indicator.py

import pandas as pd
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class WhaleIndicator(BaseIndicator):
    """
    ماژول پیشرفته برای شناسایی فعالیت‌های غیرعادی حجم که می‌تواند نشانه
    حضور و فعالیت بازیگران بزرگ بازار (نهنگ‌ها) باشد.
    """

    def __init__(self, df: pd.DataFrame, period: int = 20, spike_multiplier: float = 3.5, **kwargs):
        """
        سازنده کلاس.
        Args:
            df (pd.DataFrame): دیتافریم OHLCV.
            period (int): دوره زمانی برای محاسبه میانگین حجم.
            spike_multiplier (float): ضریبی که مشخص می‌کند حجم فعلی چند برابر میانگین باشد
                                     تا به عنوان اسپایک در نظر گرفته شود.
        """
        super().__init__(df, period=period, spike_multiplier=spike_multiplier, **kwargs)
        self.period = period
        self.spike_multiplier = spike_multiplier
        self.vol_ma_col = f'volume_ma_{period}'

    def calculate(self) -> pd.DataFrame:
        """
        میانگین حجم را محاسبه کرده و به دیتافریم اضافه می‌کند.
        """
        self.df[self.vol_ma_col] = self.df['volume'].rolling(window=self.period, min_periods=self.period).mean()
        return self.df

    def analyze(self) -> dict:
        """
        آخرین کندل را برای فعالیت نهنگ‌ها تحلیل می‌کند.
        """
        if self.vol_ma_col not in self.df.columns or self.df[self.vol_ma_col].isnull().all():
            return {"status": "Not Enough Data", "spike_factor": 0, "pressure": "Unknown"}

        last_candle = self.df.iloc[-1]
        
        last_volume = last_candle['volume']
        avg_volume = last_candle[self.vol_ma_col]
        
        status = "Normal Activity"
        pressure = "Neutral"
        spike_factor = 0
        
        if avg_volume > 0:
            spike_factor = round(last_volume / avg_volume, 2)
        
        # ۱. بررسی وجود اسپایک حجمی
        if spike_factor > self.spike_multiplier:
            status = "Whale Activity Detected"
            
            # ۲. تحلیل فشار خرید یا فروش
            if last_candle['close'] > last_candle['open']:
                pressure = "Buying Pressure"
            elif last_candle['close'] < last_candle['open']:
                pressure = "Selling Pressure"
            else:
                pressure = "Indecisive" # کندل دوجی

        return {
            "status": status,
            "spike_factor": spike_factor,
            "pressure": pressure
        }
