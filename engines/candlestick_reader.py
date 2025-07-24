candlestick_reader_advanced.py

نسخه نهایی و فوق‌پیشرفته کندل‌خوانی با فیلتر هوشمند و ویژوالیزیشن داخلی

شامل تمام الگوهای کلاسیک، حرفه‌ای، و برگشتی مهم بازار

import pandas as pd import numpy as np import mplfinance as mpf from datetime import datetime

class CandlestickPatternDetector: def init(self, df): self.df = df.copy() self.patterns = []

def detect_patterns(self):
    self.patterns = []
    for i in range(2, len(self.df)):
        row = self.df.iloc[i]
        prev = self.df.iloc[i - 1]
        prev2 = self.df.iloc[i - 2]

        body = abs(row['close'] - row['open'])
        upper_shadow = row['high'] - max(row['close'], row['open'])
        lower_shadow = min(row['close'], row['open']) - row['low']
        total_range = row['high'] - row['low']

        pattern = None
        score = 0

        # Engulfing Patterns
        if row['close'] > row['open'] and prev['close'] < prev['open'] and \
           row['close'] > prev['open'] and row['open'] < prev['close']:
            pattern = "Bullish Engulfing"
            score = 1.5

        elif row['close'] < row['open'] and prev['close'] > prev['open'] and \
             row['open'] > prev['close'] and row['close'] < prev['open']:
            pattern = "Bearish Engulfing"
            score = 1.5

        # Hammer
        elif body < total_range * 0.3 and lower_shadow > 2 * body and upper_shadow < body:
            pattern = "Hammer"
            score = 1.2

        # Inverted Hammer
        elif body < total_range * 0.3 and upper_shadow > 2 * body and lower_shadow < body:
            pattern = "Inverted Hammer"
            score = 1.2

        # Doji
        elif body < total_range * 0.1:
            pattern = "Doji"
            score = 1.0

        # Morning Star
        elif prev2['close'] < prev2['open'] and abs(prev['close'] - prev['open']) < (prev2['open'] - prev2['close']) * 0.5 and \
             row['close'] > row['open'] and row['close'] > (prev2['open'] + prev2['close']) / 2:
            pattern = "Morning Star"
            score = 2.0

        # Evening Star
        elif prev2['close'] > prev2['open'] and abs(prev['close'] - prev['open']) < (prev2['close'] - prev2['open']) * 0.5 and \
             row['close'] < row['open'] and row['close'] < (prev2['open'] + prev2['close']) / 2:
            pattern = "Evening Star"
            score = 2.0

        # Shooting Star
        elif body < total_range * 0.3 and upper_shadow > 2 * body and lower_shadow < body and row['close'] < row['open']:
            pattern = "Shooting Star"
            score = 1.3

        # Hanging Man
        elif body < total_range * 0.3 and lower_shadow > 2 * body and upper_shadow < body and row['close'] < row['open']:
            pattern = "Hanging Man"
            score = 1.3

        # Piercing Pattern
        elif prev['close'] < prev['open'] and row['close'] > row['open'] and row['close'] > (prev['open'] + prev['close']) / 2 and \
             row['open'] < prev['low']:
            pattern = "Piercing Pattern"
            score = 1.4

        # Dark Cloud Cover
        elif prev['close'] > prev['open'] and row['close'] < row['open'] and row['close'] < (prev['open'] + prev['close']) / 2 and \
             row['open'] > prev['high']:
            pattern = "Dark Cloud Cover"
            score = 1.4

        # Tweezer Top / Bottom
        elif abs(row['high'] - prev['high']) < 1e-3:
            pattern = "Tweezer Top" if row['close'] < row['open'] else "Tweezer Bottom"
            score = 1.2

        self.patterns.append({
            "index": i,
            "pattern": pattern,
            "score": score,
            "volume": row['volume']
        })

    return self.patterns

def apply_filters(self, min_score=1.2, min_volume_ratio=1.0):
    if not self.patterns:
        self.detect_patterns()

    volume_mean = self.df['volume'].rolling(window=20).mean()
    filtered = []

    for p in self.patterns:
        if p['pattern'] is None:
            continue
        vol = self.df.iloc[p['index']]['volume']
        vol_avg = volume_mean.iloc[p['index']]
        if p['score'] >= min_score and vol > (vol_avg * min_volume_ratio):
            filtered.append(p)

    return filtered

def visualize(self, title="Candlestick Chart with Patterns"):
    df_plot = self.df.copy()
    df_plot.index = pd.to_datetime(df_plot['timestamp'])
    df_plot = df_plot[['open', 'high', 'low', 'close', 'volume']]

    patterns_df = pd.DataFrame(self.patterns)
    markers = []

    for i, row in patterns_df.iterrows():
        if pd.isna(row['pattern']):
            continue
        candle_row = self.df.iloc[int(row['index'])]
        y_pos = candle_row['high'] + (candle_row['high'] * 0.005)
        marker = mpf.make_addplot(
            [np.nan if j != row['index'] else y_pos for j in range(len(self.df))],
            type='scatter', markersize=100,
            marker='^' if candle_row['close'] > candle_row['open'] else 'v',
            color='green' if candle_row['close'] > candle_row['open'] else 'red')
        markers.append(marker)

    mpf.plot(df_plot, type='candle', style='yahoo', volume=True, addplot=markers, title=title)

=== مثال استفاده ===

if name == "main": df = pd.read_csv("sample_candles.csv")  # شامل ستون‌های: timestamp, open, high, low, close, volume reader = CandlestickPatternDetector(df) reader.detect_patterns() filtered_patterns = reader.apply_filters(min_score=1.2, min_volume_ratio=1.0)

print("Filtered Patterns:")
for p in filtered_patterns:
    print(p)

reader.visualize("نمودار کندل با الگوهای فیلتر شده")

