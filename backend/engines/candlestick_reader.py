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
        self.trend_signal = self.context.get("trend", {}).get("signal", "Neutral")
        self.pivots = self.context.get("market_structure", {}).get("pivots", [])
        self.atr = self.context.get("indicators", {}).get("atr", 0)
        if self.atr == 0:
            self.atr = (self.df['high'] - self.df['low']).dropna().mean() or 0

    def _is_near_pivot(self, index: int) -> bool:
        if not self.pivots or self.atr == 0: return False
        current_price = self.df.iloc[index]['close']
        for _, p_price, _ in self.pivots:
            if abs(current_price - p_price) < (self.atr * 0.5):
                return True
        return False

    def detect_high_quality_patterns(self) -> List[str]:
        self.patterns = []
        is_uptrend = "Uptrend" in self.trend_signal
        is_downtrend = "Downtrend" in self.trend_signal
        volume_mean = self.df['volume'].rolling(window=20, min_periods=1).mean()

        for i in range(2, len(self.df)):
            row = self.df.iloc[i]
            prev = self.df.iloc[i - 1]
            prev2 = self.df.iloc[i - 2]
            body = abs(row['close'] - row['open'])
            total_range = row['high'] - row['low']
            if total_range == 0:
                continue

            pattern = None

            # Bullish Engulfing
            if is_uptrend or self._is_near_pivot(i):
                if prev['close'] < prev['open'] and row['close'] > row['open'] and row['close'] >= prev['open'] and row['open'] <= prev['close']:
                    pattern = "Bullish Engulfing"

            # Bearish Engulfing
            if is_downtrend or self._is_near_pivot(i):
                if prev['close'] > prev['open'] and row['close'] < row['open'] and row['close'] <= prev['open'] and row['open'] >= prev['close']:
                    pattern = "Bearish Engulfing"

            # Hammer
            if body / total_range < 0.4 and (row['low'] < min(prev['low'], prev2['low'])):
                if (row['close'] > row['open']) and ((row['open'] - row['low']) > 2 * body):
                    pattern = "Hammer"

            # Hanging Man
            if body / total_range < 0.4 and (row['high'] > max(prev['high'], prev2['high'])):
                if (row['close'] < row['open']) and ((row['open'] - row['low']) > 2 * body):
                    pattern = "Hanging Man"

            # Doji
            if abs(row['close'] - row['open']) <= total_range * 0.05:
                pattern = "Doji"

            # Morning Star
            if is_downtrend:
                if prev2['close'] < prev2['open'] and abs(prev['close'] - prev['open']) < body and row['close'] > (prev2['open'] + prev2['close']) / 2:
                    pattern = "Morning Star"

            # Evening Star
            if is_uptrend:
                if prev2['close'] > prev2['open'] and abs(prev['close'] - prev['open']) < body and row['close'] < (prev2['open'] + prev2['close']) / 2:
                    pattern = "Evening Star"

            # Shooting Star
            upper_shadow = row['high'] - max(row['close'], row['open'])
            lower_shadow = min(row['close'], row['open']) - row['low']
            if upper_shadow > 2 * body and lower_shadow < body:
                pattern = "Shooting Star"

            # Inverted Hammer
            if upper_shadow > 2 * body and lower_shadow < body and (is_downtrend or self._is_near_pivot(i)):
                pattern = "Inverted Hammer"

            # Three White Soldiers
            if i >= 3:
                r1 = self.df.iloc[i - 2]
                r2 = self.df.iloc[i - 1]
                r3 = self.df.iloc[i]
                if all(r['close'] > r['open'] for r in [r1, r2, r3]):
                    if r2['open'] > r1['open'] and r3['open'] > r2['open']:
                        pattern = "Three White Soldiers"

            # Three Black Crows
            if i >= 3:
                r1 = self.df.iloc[i - 2]
                r2 = self.df.iloc[i - 1]
                r3 = self.df.iloc[i]
                if all(r['close'] < r['open'] for r in [r1, r2, r3]):
                    if r2['open'] < r1['open'] and r3['open'] < r2['open']:
                        pattern = "Three Black Crows"

            # Tweezer Bottom
            if abs(prev['low'] - row['low']) < self.atr * 0.1:
                pattern = "Tweezer Bottom"

            # Tweezer Top
            if abs(prev['high'] - row['high']) < self.atr * 0.1:
                pattern = "Tweezer Top"

            # Piercing Line
            if prev['close'] < prev['open'] and row['open'] < row['low'] and row['close'] > (prev['open'] + prev['close']) / 2:
                pattern = "Piercing Line"

            # Dark Cloud Cover
            if prev['close'] > prev['open'] and row['open'] > prev['high'] and row['close'] < (prev['open'] + prev['close']) / 2:
                pattern = "Dark Cloud Cover"

            # Marubozu
            if abs(row['high'] - row['close']) < self.atr * 0.05 and abs(row['open'] - row['low']) < self.atr * 0.05:
                pattern = "Bullish Marubozu" if row['close'] > row['open'] else "Bearish Marubozu"

            # Confirm volume
            if pattern:
                avg_volume = volume_mean.iloc[i]
                if pd.notna(avg_volume) and row['volume'] > avg_volume * 1.1:
                    self.patterns.append(pattern)

        return list(set(self.patterns))
