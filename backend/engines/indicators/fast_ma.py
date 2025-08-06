import pandas as pd
import numpy as np
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class FastMAIndicator(BaseIndicator):
    """
    پیاده‌سازی یکپارچه برای اندیکاتورهای DEMA (Double Exponential Moving Average)
    و TEMA (Triple Exponential Moving Average) برای کاهش تاخیر.
    """

    def calculate(self) -> pd.DataFrame:
        """
        محاسبه DEMA یا TEMA بر اساس پارامتر ورودی ma_type.

        Returns:
            pd.DataFrame: دیتافریم به‌روز شده با ستون اندیکاتور.
        """
        self.period = self.params.get('period', 14)
        self.ma_type = self.params.get('ma_type', 'DEMA').upper()
        
        if self.ma_type not in ['DEMA', 'TEMA']:
            raise ValueError(f"Invalid ma_type: {self.ma_type}. Must be 'DEMA' or 'TEMA'.")

        close_col = self.params.get('close_col', 'close')
        if close_col not in self.df.columns:
            raise ValueError(f"Column '{close_col}' not found in the DataFrame.")

        logger.debug(f"Calculating {self.ma_type} with period={self.period}")
        
        # --- محاسبات پایه ---
        ema1 = self.df[close_col].ewm(span=self.period, adjust=False).mean()
        ema2 = ema1.ewm(span=self.period, adjust=False).mean()
        
        self.col_name = f"{self.ma_type.lower()}_{self.period}"

        # --- اعمال فرمول بر اساس نوع ---
        if self.ma_type == 'DEMA':
            # Formula: DEMA = 2 * EMA(n) - EMA(EMA(n))
            self.df[self.col_name] = 2 * ema1 - ema2
        
        elif self.ma_type == 'TEMA':
            # Formula: TEMA = 3*EMA(n) - 3*EMA(EMA(n)) + EMA(EMA(EMA(n)))
            ema3 = ema2.ewm(span=self.period, adjust=False).mean()
            self.df[self.col_name] = 3 * ema1 - 3 * ema2 + ema3
            
        return self.df

    def analyze(self) -> dict:
        """
        تحلیل موقعیت قیمت و شیب خط DEMA/TEMA.

        Returns:
            dict: یک دیکشنری حاوی تحلیل نهایی.
        """
        if len(self.df) < 2:
            return {'signal': 'neutral', 'message': 'Not enough data for analysis.'}
            
        last_row = self.df.iloc[-1]
        prev_row = self.df.iloc[-2]
        
        close_price = last_row[self.params.get('close_col', 'close')]
        ma_value = last_row[self.col_name]
        prev_ma_value = prev_row[self.col_name]
        
        analysis = {
            'indicator': self.ma_type,
            'params': {'period': self.period},
            'values': {
                'close': close_price,
                self.ma_type.lower(): round(ma_value, 4)
            }
        }

        # تعیین شیب خط
        is_rising = ma_value > prev_ma_value
        is_falling = ma_value < prev_ma_value

        if close_price > ma_value and is_rising:
            analysis['signal'] = 'buy'
            analysis['message'] = f"Price is above {self.ma_type} and the slope is rising. Bullish."
        elif close_price < ma_value and is_falling:
            analysis['signal'] = 'sell'
            analysis['message'] = f"Price is below {self.ma_type} and the slope is falling. Bearish."
        else:
            analysis['signal'] = 'neutral'
            analysis['message'] = f"Price position relative to {self.ma_type} does not indicate a clear signal."
            
        return analysis

