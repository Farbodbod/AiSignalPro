# engines/market_structure_analyzer.py

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from typing import List, Dict, Any

class PivotPoint:
    # --- اصلاح شد ---
    def __init__(self, index: int, price: float, strength: str):
        self.index = index
        self.price = price
        self.strength = strength # 'major' or 'minor'

class Leg:
    # --- اصلاح شد ---
    def __init__(self, start_pivot: PivotPoint, end_pivot: PivotPoint, df: pd.DataFrame):
        self.start = start_pivot
        self.end = end_pivot
        self.length = abs(end_pivot.price - start_pivot.price)
        self.duration = abs(end_pivot.index - start_pivot.index)
        self.angle = np.degrees(np.arctan2(self.length, self.duration)) if self.duration > 0 else 0
        self.volume_sum = df['volume'][start_pivot.index:end_pivot.index].sum()
        self.score = self.calculate_score()

    def calculate_score(self):
        normalized_length = self.length / (self.duration + 1e-6)
        return round((self.angle * normalized_length * np.log1p(self.volume_sum)), 2)

class LegPivotAnalyzer:
    # --- اصلاح شد ---
    def __init__(self, df: pd.DataFrame, sensitivity: int = 5):
        self.df = df.reset_index(drop=True)
        self.sensitivity = sensitivity
        self.pivots: List[PivotPoint] = []
        self.legs: List[Leg] = []
        self.market_phase = None
        self.patterns: List[str] = []
        self.anomalies: List[Dict[str, Any]] = []

    def detect_pivots(self):
        prices = self.df['close']
        for i in range(self.sensitivity, len(prices) - self.sensitivity):
            window = prices[i - self.sensitivity:i + self.sensitivity + 1]
            if prices[i] == window.min():
                self.pivots.append(PivotPoint(i, prices[i], 'minor'))
            elif prices[i] == window.max():
                self.pivots.append(PivotPoint(i, prices[i], 'minor'))
        self._refine_major_pivots()

    def _refine_major_pivots(self):
        if not self.pivots: return
        refined = []
        for i, p in enumerate(self.pivots):
            is_major = (i == 0 or i == len(self.pivots) - 1 or abs(p.price - self.pivots[i - 1].price) > self.df['close'].std())
            if is_major:
                refined.append(PivotPoint(p.index, p.price, 'major'))
        self.pivots = refined

    def build_legs(self):
        if len(self.pivots) < 2: return
        for i in range(len(self.pivots) - 1):
            leg = Leg(self.pivots[i], self.pivots[i + 1], self.df)
            self.legs.append(leg)

    def detect_market_phase(self):
        if not self.legs:
            self.market_phase = 'undetermined'
            return
        avg_angle = np.mean([leg.angle for leg in self.legs])
        if avg_angle < 15: self.market_phase = 'ranging'
        elif avg_angle < 40: self.market_phase = 'weak_trend'
        else: self.market_phase = 'strong_trend'

    def detect_patterns(self):
        if len(self.legs) < 2: return
        for i in range(len(self.legs) - 2):
            l1, l2 = self.legs[i], self.legs[i + 1]
            if l1.length > 0.8 * l2.length and abs(l1.angle - l2.angle) < 10:
                self.patterns.append('Double Top/Bottom')
            if l1.angle > 45 and l2.angle < -45:
                self.patterns.append('Flag Reversal')

    def detect_anomalies(self):
        if not self.legs: return
        scores = [leg.score for leg in self.legs]
        if not scores: return
        threshold = np.percentile(scores, 90)
        for leg in self.legs:
            if leg.score > threshold * 1.5:
                self.anomalies.append({'start': leg.start.index, 'end': leg.end.index, 'score': leg.score, 'type': 'high_strength'})

    def ml_predict_next_leg_direction(self):
        if len(self.legs) < 6: return None
        features = [[leg.angle, leg.duration, leg.length, leg.volume_sum, leg.score] for leg in self.legs]
        labels = [1 if self.legs[i + 1].end.price > self.legs[i].end.price else 0 for i in range(len(self.legs) - 1)]
        X, y = features[:-1], labels
        
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        clf = RandomForestClassifier(n_estimators=50, random_state=42)
        clf.fit(X_scaled, y)
        
        next_feature = scaler.transform([features[-1]])
        prediction = clf.predict(next_feature)
        return 'up' if prediction[0] == 1 else 'down'

    def analyze(self):
        self.detect_pivots()
        self.build_legs()
        self.detect_market_phase()
        self.detect_patterns()
        self.detect_anomalies()
        next_direction = self.ml_predict_next_leg_direction()
        
        return {
            'pivots': [(p.index, p.price, p.strength) for p in self.pivots],
            'legs_count': len(self.legs),
            'market_phase': self.market_phase,
            'patterns': list(set(self.patterns)), # remove duplicates
            'anomalies': self.anomalies,
            'predicted_next_leg_direction': next_direction
        }
