# engines/market_structure_analyzer.py (نسخه کاملاً نهایی 4.2)

import numpy as np
import pandas as pd
from typing import List, Dict, Any

class MarketStructureAnalyzer:
    def __init__(self, df: pd.DataFrame, config: Dict[str, Any]):
        self.df = df.copy().reset_index(drop=True)
        self.config = config
        self.sensitivity = self.config.get('sensitivity', 7)
        self.cluster_strength = self.config.get('sr_cluster_strength', 0.02)
        self.pivots: List[Dict] = []
        if 'atr' not in self.df.columns or self.df['atr'].isnull().all():
            tr1 = self.df['high'] - self.df['low']
            tr2 = np.abs(self.df['high'] - self.df['close'].shift())
            tr3 = np.abs(self.df['low'] - self.df['close'].shift())
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            self.df['atr'] = tr.rolling(window=14).mean()

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
        return {"point_of_control": poc.get('price')}

    def analyze(self) -> Dict[str, Any]:
        self._detect_pivots()
        vp_analysis = self._calculate_volume_profile()
        
        key_levels = {}
        poc = vp_analysis.get("point_of_control")
        if poc:
            key_levels['point_of_control'] = poc
        
        recent_pivots = self.pivots[-10:]
        supports = sorted([p['price'] for p in recent_pivots if p['type'] == 'low'], reverse=True)
        resistances = sorted([p['price'] for p in recent_pivots if p['type'] == 'high'])
        
        key_levels['supports'] = supports[:5]
        key_levels['resistances'] = resistances[:5]

        return {
            "pivots": self.pivots,
            "key_levels": key_levels
        }
