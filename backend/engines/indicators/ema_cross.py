import pandas as pd
import numpy as np
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class EMACrossIndicator(BaseIndicator):
    """
    پیاده‌سازی اندیکاتور EMA Cross بر اساس ساختار پروژه AiSignalPro.
    این اندیکاتور از BaseIndicator ارث‌بری کرده و متدهای calculate و analyze را پیاده‌سازی می‌کند.
    """

    def calculate(self) -> pd.DataFrame:
        """
        محاسبه مقادیر EMA کوتاه مدت و بلند مدت و همچنین سیگنال تقاطع.
        نتایج به صورت ستون‌های جدید به self.df اضافه می‌شوند.

        Returns:
            pd.DataFrame: دیتافریم به‌روز شده با ستون‌های محاسبه شده.
        """
        self.short_period = self.params.get('short_period', 9)
        self.long_period = self.params.get('long_period', 21)

        if self.short_period >= self.long_period:
            raise ValueError(f"Short period ({self.short_period}) must be less than long period ({self.long_period}).")
        
        close_col = self.params.get('close_col', 'close')
        if close_col not in self.df.columns:
            raise ValueError(f"Column '{close_col}' not found in the DataFrame.")
            
        logger.debug(f"Calculating EMA Cross with short={self.short_period}, long={self.long_period}")

        # --- EMA Calculation ---
        short_ema_col = f'ema_{self.short_period}'
        long_ema_col = f'ema_{self.long_period}'
        
        self.df[short_ema_col] = self.df[close_col].ewm(span=self.short_period, adjust=False).mean()
        self.df[long_ema_col] = self.df[close_col].ewm(span=self.long_period, adjust=False).mean()

        # --- Crossover Signal Generation (Vectorized & Efficient) ---
        self.signal_col_name = f'signal_ema_cross_{self.short_period}_{self.long_period}'
        
        prev_short_ema = self.df[short_ema_col].shift(1)
        prev_long_ema = self.df[long_ema_col].shift(1)

        condition_bullish = (prev_short_ema < prev_long_ema) & (self.df[short_ema_col] > self.df[long_ema_col])
        condition_bearish = (prev_short_ema > prev_long_ema) & (self.df[short_ema_col] < self.df[long_ema_col])

        self.df[self.signal_col_name] = np.where(condition_bullish, 1, np.where(condition_bearish, -1, 0))
        
        return self.df

    def analyze(self) -> dict:
        """
        تحلیل آخرین سیگنال تولید شده توسط اندیکاتور.

        Returns:
            dict: یک دیکشنری حاوی تحلیل نهایی (signal, value).
        """
        last_row = self.df.iloc[-1]
        signal_value = int(last_row[self.signal_col_name])

        analysis = {
            'indicator': self.__class__.__name__,
            'params': {'short': self.short_period, 'long': self.long_period}
        }

        if signal_value == 1:
            analysis['signal'] = 'buy'
            analysis['message'] = f"Golden Cross ({self.short_period}/{self.long_period}): Short EMA crossed above Long EMA."
        elif signal_value == -1:
            analysis['signal'] = 'sell'
            analysis['message'] = f"Death Cross ({self.short_period}/{self.long_period}): Short EMA crossed below Long EMA."
        else:
            analysis['signal'] = 'neutral'
            analysis['message'] = "No EMA crossover detected in the last candle."
            
        analysis['values'] = {
            f'ema_{self.short_period}': round(last_row[f'ema_{self.short_period}'], 4),
            f'ema_{self.long_period}': round(last_row[f'ema_{self.long_period}'], 4)
        }
        
        return analysis

