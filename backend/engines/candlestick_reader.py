# engines/candlestick_reader.py (نسخه نهایی 3.0 - جامع و کاملاً سازگار)

import pandas as pd
import numpy as np
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class CandlestickPatternDetector:
    def __init__(self, df: pd.DataFrame, analysis_context: Dict[str, Any]):
        if not isinstance(df, pd.DataFrame) or df.empty:
            raise ValueError("Input must be a non-empty pandas DataFrame.")
        
        self.df = df.copy().reset_index(drop=True)
        self.context = analysis_context
        self.patterns = []
        
        # دریافت داده‌های لازم از کانتکست تحلیلی
        self.trend_signal = self.context.get("trend", {}).get("signal", "Neutral")
        self.pivots = self.context.get("market_structure", {}).get("pivots", [])
        self.atr = self.context.get("indicators", {}).get("atr", 0)
        
        # اطمینان از معتبر بودن ATR برای جلوگیری از خطا
        if self.atr == 0 or pd.isna(self.atr):
            self.atr = (self.df['high'] - self.df['low']).dropna().mean()
            if not self.atr or self.atr == 0:
                self.atr = 1e-9 # یک مقدار بسیار کوچک برای جلوگیری از تقسیم بر صفر

    def _is_near_pivot(self, index: int) -> bool:
        """ بررسی می‌کند که آیا کندل فعلی به یک ناحیه پیوت مهم نزدیک است یا خیر. """
        if not self.pivots: return False
        current_price = self.df.iloc[index]['close']
        
        # حلقه اصلاح شده برای کار با لیست دیکشنری‌ها
        for pivot in self.pivots:
            p_price = pivot.get('price')
            if p_price is not None:
                if abs(current_price - p_price) < (self.atr * 0.5):
                    return True
        return False

    def detect_high_quality_patterns(self) -> List[str]:
        """ تمام الگوهای شمعی معتبر را با تاییدیه حجم و شرایط بازار شناسایی می‌کند. """
        self.patterns = []
        is_uptrend = "Uptrend" in self.trend_signal
        is_downtrend = "Downtrend" in self.trend_signal
        volume_mean = self.df['volume'].rolling(window=20, min_periods=1).mean()
        df_len = len(self.df)

        for i in range(2, df_len):
            if i >= df_len: continue

            row = self.df.iloc[i]
            prev = self.df.iloc[i - 1]
            prev2 = self.df.iloc[i - 2]

            body = abs(row['close'] - row['open'])
            total_range = row['high'] - row['low']
            if total_range == 0: continue
            
            upper_shadow = row['high'] - max(row['open'], row['close'])
            lower_shadow = min(row['open'], row['close']) - row['low']
            
            pattern = None

            # --- بازگردانی و بهینه‌سازی تمام الگوهای جامع از کد اولیه شما ---

            if prev['close'] < prev['open'] and row['close'] > row['open'] and row['close'] >= prev['open'] and row['open'] <= prev['close']:
                pattern = "Bullish Engulfing"
            elif prev['close'] > prev['open'] and row['close'] < row['open'] and row['close'] <= prev['open'] and row['open'] >= prev['close']:
                pattern = "Bearish Engulfing"
            elif lower_shadow > 2 * body and upper_shadow < body and is_downtrend:
                pattern = "Hammer"
            elif upper_shadow > 2 * body and lower_shadow < body and is_uptrend:
                pattern = "Shooting Star"
            elif abs(row['close'] - row['open']) / total_range < 0.1 and (is_downtrend or is_uptrend):
                pattern = "Doji"
            elif is_downtrend and prev2['close'] < prev2['open'] and prev['close'] < prev2['close'] and body < abs(prev['close'] - prev['open']) and row['close'] > prev['open'] and row['close'] > (prev2['open'] + prev2['close']) / 2:
                pattern = "Morning Star"
            elif is_uptrend and prev2['close'] > prev2['open'] and prev['close'] > prev2['close'] and body < abs(prev['close'] - prev['open']) and row['close'] < prev['open'] and row['close'] < (prev2['open'] + prev2['close']) / 2:
                pattern = "Evening Star"
            elif i >= 3:
                r1, r2, r3 = self.df.iloc[i-2], self.df.iloc[i-1], self.df.iloc[i]
                if all(r['close'] > r['open'] for r in [r1, r2, r3]) and r2['open'] > r1['open'] and r3['open'] > r2['open'] and r2['close'] > r1['close'] and r3['close'] > r2['close']:
                    pattern = "Three White Soldiers"
                elif all(r['close'] < r['open'] for r in [r1, r2, r3]) and r2['open'] < r1['open'] and r3['open'] < r2['open'] and r2['close'] < r1['close'] and r3['close'] < r2['close']:
                    pattern = "Three Black Crows"
            
            # افزودن تاییدیه اضافی: الگو در نزدیکی یک پیوت مهم رخ دهد
            if pattern and self._is_near_pivot(i):
                # تایید نهایی با حجم معاملات
                avg_volume = volume_mean.iloc[i]
                if pd.notna(avg_volume) and row['volume'] > avg_volume * 1.2: # کمی سخت‌گیرانه‌تر کردن فیلتر حجم
                    self.patterns.append(pattern)

        return list(set(self.patterns))

