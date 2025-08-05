# engines/indicators/structure_indicator.py

import numpy as np
import pandas as pd
from typing import List, Dict, Any
from .base import BaseIndicator
import logging

logger = logging.getLogger(__name__)

class StructureIndicator(BaseIndicator):
    """
    ماژول پیشرفته برای تحلیل ساختار بازار. این ماژول قابلیت‌های زیر را دارد:
    - شناسایی نقاط پیوت ساختاری (Swing Highs/Lows).
    - محاسبه پروفایل حجم و نقطه کنترل (Point of Control - POC).
    - استخراج سطوح کلیدی حمایت و مقاومت بر اساس این تحلیل‌ها.
    """
    def __init__(self, df: pd.DataFrame, sensitivity: int = 7, **kwargs):
        super().__init__(df, sensitivity=sensitivity, **kwargs)
        self.sensitivity = sensitivity
        self.pivots: List[Dict] = []

    def calculate(self) -> pd.DataFrame:
        """
        این متد محاسبات را انجام داده و نتایج را در متغیرهای کلاس ذخیره می‌کند.
        """
        self._detect_pivots()
        return self.df

    def _detect_pivots(self):
        """پیوت‌های ساختاری (نقاط چرخش قیمت) را شناسایی می‌کند."""
        lows, highs = [], []
        df_len = len(self.df)
        if df_len <= 2 * self.sensitivity:
            return # داده کافی برای یافتن پیوت وجود ندارد

        for i in range(self.sensitivity, df_len - self.sensitivity):
            window = self.df.iloc[i - self.sensitivity : i + self.sensitivity + 1]
            if self.df['low'].iloc[i] <= window['low'].min():
                lows.append({'index': i, 'price': self.df['low'].iloc[i], 'type': 'low'})
            if self.df['high'].iloc[i] >= window['high'].max():
                highs.append({'index': i, 'price': self.df['high'].iloc[i], 'type': 'high'})
        
        raw_pivots = sorted(lows + highs, key=lambda p: p['index'])
        if not raw_pivots: return
        
        # فیلتر کردن پیوت‌ها برای داشتن ترتیب متناوب سقف و کف
        self.pivots.append(raw_pivots[0])
        for i in range(1, len(raw_pivots)):
            if raw_pivots[i]['type'] != self.pivots[-1]['type']:
                self.pivots.append(raw_pivots[i])

    def _calculate_volume_profile(self) -> Dict[str, Any]:
        """پروفایل حجم را در بازه دیتافریم محاسبه کرده و POC را برمی‌گرداند."""
        if self.df.empty or 'volume' not in self.df.columns or self.df['volume'].sum() == 0:
            return {}

        price_bins = np.linspace(self.df['low'].min(), self.df['high'].max(), 100)
        volume_at_price = [self.df['volume'][(self.df['low'] <= p) & (self.df['high'] >= p)].sum() for p in price_bins]
        
        volume_profile = pd.DataFrame({'price': price_bins, 'volume': volume_at_price}).dropna()
        if volume_profile.empty: return {}

        poc_index = volume_profile['volume'].idxmax()
        poc = volume_profile.loc[poc_index, 'price']
        return {"point_of_control": poc}

    def analyze(self) -> dict:
        """
        نتایج تحلیل ساختار بازار را در یک دیکشنری جامع برمی‌گرداند.
        """
        vp_analysis = self._calculate_volume_profile()
        
        key_levels = {}
        poc = vp_analysis.get("point_of_control")
        if poc:
            key_levels['point_of_control'] = poc
        
        recent_pivots = self.pivots[-20:] # بررسی ۲۰ پیوت آخر برای یافتن سطوح
        supports = sorted(list(set([p['price'] for p in recent_pivots if p['type'] == 'low'])), reverse=True)
        resistances = sorted(list(set([p['price'] for p in recent_pivots if p['type'] == 'high'])))
        
        key_levels['supports'] = supports[:5] # ۵ سطح حمایت کلیدی آخر
        key_levels['resistances'] = resistances[:5] # ۵ سطح مقاومت کلیدی آخر

        return {
            "pivots_count": len(self.pivots),
            "key_levels": key_levels
        }
