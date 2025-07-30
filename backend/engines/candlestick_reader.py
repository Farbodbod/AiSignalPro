# engines/candlestick_reader.py (نسخه نهایی و هوشمند مبتنی بر زمینه)

import pandas as pd
import numpy as np
from typing import Dict, Any, List

class CandlestickPatternDetector:
    def __init__(self, df: pd.DataFrame, analysis_context: Dict[str, Any]):
        """
        این نسخه جدید، علاوه بر دیتافریم، به زمینه تحلیلی (شامل روند و پیوت ها) نیز دسترسی دارد.
        """
        if not isinstance(df, pd.DataFrame) or df.empty:
            raise ValueError("Input must be a non-empty pandas DataFrame.")
        
        self.df = df.copy().reset_index(drop=True)
        self.context = analysis_context
        self.patterns = []
        # استخراج داده های مورد نیاز از کانتکست
        self.trend_signal = self.context.get("trend", {}).get("signal", "Neutral")
        self.pivots = self.context.get("market_structure", {}).get("pivots", [])
        self.atr = self.context.get("indicators", {}).get("atr", 0)
        if self.atr == 0: # Fallback in case ATR is not calculated
            self.atr = (self.df['high'] - self.df['low']).mean()

    def _is_near_pivot(self, index: int) -> bool:
        """بررسی می کند که آیا کندل در نزدیکی یک سطح پیوت مهم قرار دارد یا خیر."""
        if not self.pivots or self.atr == 0:
            return False
        
        current_price = self.df.iloc[index]['close']
        for p_index, p_price, p_strength in self.pivots:
            # اگر الگو در فاصله کمتر از نصف ATR از یک پیوت باشد، معتبر است
            if abs(current_price - p_price) < (self.atr * 0.5):
                return True
        return False

    def detect_high_quality_patterns(self) -> List[str]:
        """
        فقط الگوهایی را شناسایی می کند که با روند کلی همسو باشند یا در نقاط استراتژیک (پیوت) تشکیل شوند.
        """
        self.patterns = []
        is_uptrend = "Uptrend" in self.trend_signal
        is_downtrend = "Downtrend" in self.trend_signal

        for i in range(2, len(self.df)):
            row = self.df.iloc[i]; prev = self.df.iloc[i-1]; prev2 = self.df.iloc[i-2]
            body = abs(row['close'] - row['open']); total_range = row['high'] - row['low']
            if total_range == 0: continue

            pattern_info = None

            # --- الگوهای صعودی (فقط در روند صعودی یا در نزدیکی پیوت بررسی می شوند) ---
            if is_uptrend or self._is_near_pivot(i):
                is_bullish_engulfing = prev['close'] < prev['open'] and row['close'] > row['open'] and row['close'] >= prev['open'] and row['open'] <= prev['close']
                if is_bullish_engulfing:
                    pattern_info = {"pattern": "Bullish Engulfing"}

                lower_shadow = min(row['close'], row['open']) - row['low']
                if body / total_range < 0.3 and lower_shadow > 2 * body:
                    pattern_info = {"pattern": "Hammer"}
                
                is_morning_star = prev2['close'] < prev2['open'] and abs(prev['close'] - prev['open']) < abs(prev2['open'] - prev2['close']) * 0.3 and row['close'] > row['open'] and row['close'] > (prev2['open'] + prev2['close']) / 2
                if is_morning_star:
                    pattern_info = {"pattern": "Morning Star"}

            # --- الگوهای نزولی (فقط در روند نزولی یا در نزدیکی پیوت بررسی می شوند) ---
            if is_downtrend or self._is_near_pivot(i):
                is_bearish_engulfing = prev['close'] > prev['open'] and row['close'] < row['open'] and row['close'] <= prev['open'] and row['open'] >= prev['close']
                if is_bearish_engulfing:
                    pattern_info = {"pattern": "Bearish Engulfing"}

                upper_shadow = row['high'] - max(row['close'], row['open'])
                if body / total_range < 0.3 and upper_shadow > 2 * body:
                    pattern_info = {"pattern": "Shooting Star"}
                
                is_evening_star = prev2['close'] > prev2['open'] and abs(prev['close'] - prev['open']) < abs(prev2['close'] - prev2['open']) * 0.3 and row['close'] < row['open'] and row['close'] < (prev2['open'] + prev2['close']) / 2
                if is_evening_star:
                    pattern_info = {"pattern": "Evening Star"}

            # --- اعمال فیلتر نهایی بر اساس حجم و اضافه کردن الگوی معتبر ---
            if pattern_info:
                avg_volume = self.df['volume'].rolling(window=20).mean().iloc[i]
                if pd.notna(avg_volume) and avg_volume > 0 and row['volume'] > avg_volume * 1.1: # فیلتر حجم
                    self.patterns.append(pattern_info['pattern'])
        
        return list(set(self.patterns)) # حذف موارد تکراری
