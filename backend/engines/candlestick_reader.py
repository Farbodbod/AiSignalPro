# engines/candlestick_reader.py (نسخه نهایی و پایدار)

import pandas as pd
import numpy as np
from typing import Dict, Any, List

# اصلاح شد: استفاده از __name__ برای لاگر در تمام فایل‌ها باید رعایت شود
import logging
logger = logging.getLogger(__name__)

class CandlestickPatternDetector:
    # اصلاح شد: __init__
    def __init__(self, df: pd.DataFrame, analysis_context: Dict[str, Any]):
        if not isinstance(df, pd.DataFrame) or df.empty:
            raise ValueError("Input must be a non-empty pandas DataFrame.")
        
        self.df = df.copy().reset_index(drop=True)
        self.context = analysis_context
        self.patterns = []
        self.trend_signal = self.context.get("trend", {}).get("signal", "Neutral")
        self.pivots = self.context.get("market_structure", {}).get("pivots", [])
        self.atr = self.context.get("indicators", {}).get("atr", 0)
        if self.atr == 0:
            self.atr = (self.df['high'] - self.df['low']).dropna().mean() or 0

    def _is_near_pivot(self, index: int) -> bool:
        if not self.pivots or self.atr == 0: return False
        current_price = self.df.iloc[index]['close']
        for p_index, p_price, p_strength in self.pivots:
            if abs(current_price - p_price) < (self.atr * 0.5):
                return True
        return False

    def detect_high_quality_patterns(self) -> List[str]:
        self.patterns = []
        is_uptrend = "Uptrend" in self.trend_signal
        is_downtrend = "Downtrend" in self.trend_signal
        volume_mean = self.df['volume'].rolling(window=20, min_periods=1).mean() # min_periods=1 از NaN جلوگیری می‌کند

        for i in range(2, len(self.df)):
            row = self.df.iloc[i]; prev = self.df.iloc[i-1]; prev2 = self.df.iloc[i-2]
            body = abs(row['close'] - row['open']); total_range = row['high'] - row['low']
            if total_range == 0: continue
            pattern_info = None

            # ... (منطق شناسایی الگوها مثل قبل) ...
            if is_uptrend or self._is_near_pivot(i):
                is_bullish_engulfing = prev['close'] < prev['open'] and row['close'] > row['open'] and row['close'] >= prev['open'] and row['open'] <= prev['close']
                if is_bullish_engulfing: pattern_info = {"pattern": "Bullish Engulfing"}
            if is_downtrend or self._is_near_pivot(i):
                is_bearish_engulfing = prev['close'] > prev['open'] and row['close'] < row['open'] and row['close'] <= prev['open'] and row['open'] >= prev['close']
                if is_bearish_engulfing: pattern_info = {"pattern": "Bearish Engulfing"}

            if pattern_info:
                avg_volume = volume_mean.iloc[i]
                # اصلاح شد: بررسی NaN قبل از استفاده
                if pd.notna(avg_volume) and avg_volume > 0 and row['volume'] > avg_volume * 1.1:
                    self.patterns.append(pattern_info['pattern'])
        
        return list(set(self.patterns))
