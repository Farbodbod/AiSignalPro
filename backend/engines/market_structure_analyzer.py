# engines/market_structure_analyzer.py (نسخه نهایی با import صحیح)

import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional # <-- کلمه Optional اینجا اضافه شد

class PivotPoint:
    def __init__(self, index: int, price: float, strength: str):
        self.index = index
        self.price = price
        self.strength = strength

class Leg:
    def __init__(self, start_pivot: PivotPoint, end_pivot: PivotPoint, df: pd.DataFrame):
        self.start = start_pivot
        self.end = end_pivot
        self.length = abs(end_pivot.price - start_pivot.price)
        self.duration = abs(end_pivot.index - start_pivot.index)
        self.angle = np.degrees(np.arctan2(self.length, self.duration)) if self.duration > 0 else 0
        
        start_idx = max(0, self.start.index)
        end_idx = min(len(df), self.end.index)
        if start_idx < end_idx:
            self.volume_sum = df['volume'].iloc[start_idx:end_idx].sum()
        else:
            self.volume_sum = 0
            
        self.score = self.calculate_score()

    def calculate_score(self):
        normalized_length = self.length / (self.duration + 1e-6)
        return round((self.angle * normalized_length * np.log1p(self.volume_sum)), 2)

class LegPivotAnalyzer:
    def __init__(self, df: pd.DataFrame, sensitivity: int = 5):
        self.df = df.reset_index(drop=True)
        self.sensitivity = sensitivity
        self.pivots: List[PivotPoint] = []
        self.legs: List[Leg] = []
        self.market_phase = None

    def detect_pivots(self):
        prices = self.df['close']
        for i in range(self.sensitivity, len(prices) - self.sensitivity):
            window = prices.iloc[i - self.sensitivity : i + self.sensitivity + 1]
            if prices.iloc[i] == window.min():
                self.pivots.append(PivotPoint(i, prices.iloc[i], 'minor'))
            elif prices.iloc[i] == window.max():
                self.pivots.append(PivotPoint(i, prices.iloc[i], 'minor'))
        self._refine_major_pivots()

    def _refine_major_pivots(self):
        if not self.pivots: return
        atr = (self.df['high'] - self.df['low']).mean()
        if atr == 0: atr = self.df['close'].std()
        
        refined = []
        if self.pivots:
            refined.append(self.pivots[0])
            for i in range(1, len(self.pivots)):
                if abs(self.pivots[i].price - refined[-1].price) > (atr * 1.5):
                     refined.append(self.pivots[i])
            self.pivots = refined

    def build_legs(self):
        if len(self.pivots) < 2: return
        for i in range(len(self.pivots) - 1):
            leg = Leg(self.pivots[i], self.pivots[i + 1], self.df)
            self.legs.append(leg)

    def detect_market_phase(self):
        if not self.legs:
            self.market_phase = 'undetermined'; return
        angles = [leg.angle for leg in self.legs if leg.duration > 0]
        if not angles:
            self.market_phase = 'undetermined'; return
        avg_angle = np.mean(angles)
        if avg_angle < 15: self.market_phase = 'ranging'
        elif avg_angle < 40: self.market_phase = 'weak_trend'
        else: self.market_phase = 'strong_trend'

    def predict_next_leg_direction(self) -> Optional[str]:
        if len(self.pivots) < 4: return None
        last_p, second_last_p = self.pivots[-1], self.pivots[-2]
        third_last_p, fourth_last_p = self.pivots[-3], self.pivots[-4]
        
        if last_p.price > third_last_p.price and second_last_p.price > fourth_last_p.price:
            return 'up'
        elif last_p.price < third_last_p.price and second_last_p.price < fourth_last_p.price:
            return 'down'
        return 'uncertain'

    def analyze(self) -> Dict[str, Any]:
        self.detect_pivots()
        self.build_legs()
        self.detect_market_phase()
        next_direction = self.predict_next_leg_direction()
        
        return {
            'pivots': [(p.index, p.price, 'major') for p in self.pivots],
            'legs_count': len(self.legs),
            'market_phase': self.market_phase,
            'predicted_next_leg_direction': next_direction
        }
