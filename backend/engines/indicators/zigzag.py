import pandas as pd
import numpy as np
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class ZigzagIndicator(BaseIndicator):
    """
    ✨ FINAL VERSION - JSON Safe ✨
    نسخه نهایی و غیر-بازترسیم شونده ZigZag با خروجی سازگار با JSON.
    """

    def _get_pivots(self, deviation_threshold: float):
        pivots = np.zeros(len(self.df), dtype=int)
        prices = np.zeros(len(self.df), dtype=float)
        last_pivot_price = self.df['close'].iloc[0]
        last_pivot_idx = 0
        trend = 0
        
        highs = self.df['high']
        lows = self.df['low']

        for i in range(1, len(self.df)):
            current_high = highs.iloc[i]
            current_low = lows.iloc[i]

            if trend == 0:
                if current_high > last_pivot_price * (1 + deviation_threshold / 100):
                    trend = 1; last_pivot_price = current_high; last_pivot_idx = i
                elif current_low < last_pivot_price * (1 - deviation_threshold / 100):
                    trend = -1; last_pivot_price = current_low; last_pivot_idx = i
            elif trend == 1:
                if current_high > last_pivot_price:
                    last_pivot_price = current_high; last_pivot_idx = i
                elif current_low < last_pivot_price * (1 - deviation_threshold / 100):
                    pivots[last_pivot_idx] = 1; prices[last_pivot_idx] = last_pivot_price
                    trend = -1; last_pivot_price = current_low; last_pivot_idx = i
            elif trend == -1:
                if current_low < last_pivot_price:
                    last_pivot_price = current_low; last_pivot_idx = i
                elif current_high > last_pivot_price * (1 + deviation_threshold / 100):
                    pivots[last_pivot_idx] = -1; prices[last_pivot_idx] = last_pivot_price
                    trend = 1; last_pivot_price = current_high; last_pivot_idx = i
        return pivots, prices

    def calculate(self) -> pd.DataFrame:
        self.deviation_threshold = self.params.get('deviation', 5.0)
        self.col_name_pivots = f'zigzag_pivots_{self.deviation_threshold}'
        self.col_name_prices = f'zigzag_prices_{self.deviation_threshold}'
        pivots, prices = self._get_pivots(self.deviation_threshold)
        self.df[self.col_name_pivots] = pivots
        self.df[self.col_name_prices] = prices
        return self.df

    def analyze(self) -> dict:
        last_pivots = self.df[self.df[self.col_name_pivots] != 0]
        analysis = {'indicator': self.__class__.__name__, 'params': {'deviation': self.deviation_threshold}}
        if last_pivots.empty:
            analysis['signal'] = 'neutral'; analysis['message'] = "No confirmed pivots."
            return analysis

        last_pivot_row = last_pivots.iloc[-1]
        last_pivot_type = int(last_pivot_row[self.col_name_pivots])
        last_pivot_price = last_pivot_row[self.col_name_prices]
        last_pivot_time = last_pivot_row.name

        analysis['values'] = {
            'last_pivot_type': 'peak' if last_pivot_type == 1 else 'trough',
            'last_pivot_price': round(last_pivot_price, 4),
            # ✨ اصلاحیه کلیدی: تبدیل آبجکت Timestamp به متن
            'last_pivot_time': last_pivot_time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        if last_pivot_type == 1:
            analysis['signal'] = 'sell'; analysis['message'] = "Last confirmed pivot was a Peak. Trend is Down."
        elif last_pivot_type == -1:
            analysis['signal'] = 'buy'; analysis['message'] = "Last confirmed pivot was a Trough. Trend is Up."
        
        return analysis
