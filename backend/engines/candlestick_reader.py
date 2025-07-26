# candlestick_reader.py - نسخه اصلاح شده و آماده برای بک‌اند

import pandas as pd
import numpy as np
# ما دیگر به mplfinance نیازی نداریم چون در سرور قابل استفاده نیست
# import mplfinance as mpf
from datetime import datetime

class CandlestickPatternDetector:
    # مشکل اول در اینجا اصلاح شد: init -> __init__
    def __init__(self, df):
        if not isinstance(df, pd.DataFrame) or df.empty:
            raise ValueError("Input must be a non-empty pandas DataFrame.")
        
        required_columns = {'timestamp', 'open', 'high', 'low', 'close', 'volume'}
        if not required_columns.issubset(df.columns):
            raise ValueError(f"DataFrame must contain columns: {required_columns}")

        self.df = df.copy()
        self.patterns = []

    def detect_patterns(self):
        self.patterns = []
        for i in range(2, len(self.df)):
            row = self.df.iloc[i]
            prev = self.df.iloc[i-1]
            prev2 = self.df.iloc[i-2]

            body = abs(row['close'] - row['open'])
            upper_shadow = row['high'] - max(row['close'], row['open'])
            lower_shadow = min(row['close'], row['open']) - row['low']
            total_range = row['high'] - row['low']
            if total_range == 0: continue # از تقسیم بر صفر جلوگیری می‌کند

            pattern = None
            score = 0

            # الگوهای پوشا (Engulfing)
            is_bullish_engulfing = row['close'] > prev['open'] and row['open'] < prev['close'] and prev['close'] < prev['open'] and row['close'] > row['open']
            is_bearish_engulfing = row['open'] > prev['close'] and row['close'] < prev['open'] and prev['close'] > prev['open'] and row['close'] < row['open']

            if is_bullish_engulfing:
                pattern, score = "Bullish Engulfing", 1.5
            elif is_bearish_engulfing:
                pattern, score = "Bearish Engulfing", 1.5
            # چکش (Hammer)
            elif body / total_range < 0.3 and lower_shadow > 2 * body and upper_shadow < body:
                pattern, score = "Hammer", 1.2
            # چکش معکوس (Inverted Hammer)
            elif body / total_range < 0.3 and upper_shadow > 2 * body and lower_shadow < body:
                pattern, score = "Inverted Hammer", 1.2
            # ستاره صبحگاهی (Morning Star)
            elif prev2['close'] < prev2['open'] and abs(prev['close'] - prev['open']) < abs(prev2['open'] - prev2['close']) * 0.3 and row['close'] > row['open'] and row['close'] > (prev2['open'] + prev2['close']) / 2:
                pattern, score = "Morning Star", 2.0
            # ستاره عصرگاهی (Evening Star)
            elif prev2['close'] > prev2['open'] and abs(prev['close'] - prev['open']) < abs(prev2['close'] - prev2['open']) * 0.3 and row['close'] < row['open'] and row['close'] < (prev2['open'] + prev2['close']) / 2:
                pattern, score = "Evening Star", 2.0
            # ستاره ثاقب (Shooting Star)
            elif body / total_range < 0.3 and upper_shadow > 2 * body and row['open'] > row['low'] and row['close'] < row['open']:
                pattern, score = "Shooting Star", 1.3
             # دوجی (Doji)
            elif body / total_range < 0.05:
                pattern, score = "Doji", 1.0


            if pattern:
                self.patterns.append({
                    "index": i,
                    "timestamp": self.df.iloc[i]['timestamp'],
                    "pattern": pattern,
                    "score": score,
                    "volume": row['volume']
                })
        return self.patterns

    def apply_filters(self, min_score=1.2, min_volume_ratio=1.0):
        if not self.patterns:
            self.detect_patterns()

        volume_mean = self.df['volume'].rolling(window=20).mean()
        filtered_patterns = []

        for p in self.patterns:
            if p['pattern'] is None:
                continue
            
            vol = p['volume']
            vol_avg = volume_mean.iloc[p['index']]
            
            if vol_avg > 0 and p['score'] >= min_score and vol > (vol_avg * min_volume_ratio):
                filtered_patterns.append(p)

        return filtered_patterns

    # متد visualize حذف شد چون در سرور قابل استفاده نیست
