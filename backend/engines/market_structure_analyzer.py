# engines/market_structure_analyzer.py (نسخه نهایی 4.1 - کامل و بازبینی شده)

import numpy as np
import pandas as pd
from typing import List, Dict, Any
from sklearn.cluster import MeanShift

class MarketStructureAnalyzer:
    def __init__(self, df: pd.DataFrame, config: Dict[str, Any]):
        self.df = df.copy()
        self.config = config
        self.sensitivity = self.config.get('sensitivity', 7)
        self.cluster_strength = self.config.get('sr_cluster_strength', 0.02)
        self.pivots: List[Dict] = []

    def _detect_pivots(self):
        lows, highs = [], []
        df_len = len(self.df)
        for i in range(self.sensitivity, df_len - self.sensitivity):
            window = self.df.iloc[i - self.sensitivity : i + self.sensitivity + 1]
            if self.df['low'].iloc[i] <= window['low'].min():
                lows.append({'index': i, 'price': self.df['low'].iloc[i], 'type': 'low'})
            if self.df['high'].iloc[i] >= window['high'].max():
                highs.append({'index': i, 'price': self.df['high'].iloc[i], 'type': 'high'})
        
        raw_pivots = sorted(lows + highs, key=lambda p: p['index'])
        if not raw_pivots: return
        
        # حذف پیوت‌های متوالی از یک نوع
        self.pivots.append(raw_pivots[0])
        for i in range(1, len(raw_pivots)):
            if raw_pivots[i]['type'] != self.pivots[-1]['type']:
                self.pivots.append(raw_pivots[i])

    def _calculate_volume_profile(self) -> Dict[str, Any]:
        if self.df.empty or 'volume' not in self.df.columns or self.df['volume'].sum() == 0:
            return {}

        price_bins = np.linspace(self.df['low'].min(), self.df['high'].max(), 100)
        volume_at_price = [self.df['volume'][(self.df['low'] <= p) & (self.df['high'] >= p)].sum() for p in price_bins]
        
        volume_profile = pd.DataFrame({'price': price_bins, 'volume': volume_at_price}).dropna()
        if volume_profile.empty: return {}

        poc_index = volume_profile['volume'].idxmax()
        poc = volume_profile.loc[poc_index].to_dict()

        total_volume = volume_profile['volume'].sum()
        value_area_volume = total_volume * 0.7
        
        current_volume = poc['volume']
        high_idx, low_idx = poc_index, poc_index
        while current_volume < value_area_volume and (low_idx > 0 or high_idx < len(volume_profile) - 1):
            vol_above = volume_profile['volume'].get(high_idx + 1, 0)
            vol_below = volume_profile['volume'].get(low_idx - 1, 0)
            if vol_above > vol_below: high_idx += 1; current_volume += vol_above
            else: low_idx -= 1; current_volume += vol_below
        
        value_area_high = volume_profile['price'].get(high_idx, poc['price'])
        value_area_low = volume_profile['price'].get(low_idx, poc['price'])

        return {
            "point_of_control": poc.get('price'),
            "value_area_high": value_area_high,
            "value_area_low": value_area_low
        }

    def analyze(self) -> Dict[str, Any]:
        self._detect_pivots()
        volume_profile_analysis = self._calculate_volume_profile()
        return {
            "pivots": self.pivots,
            "volume_profile": volume_profile_analysis
        }
