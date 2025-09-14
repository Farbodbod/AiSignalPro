# backend/engines/indicators/ichimoku.py (v6.1 - The Convergence Signal Edition)
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class IchimokuIndicator(BaseIndicator):
    """
    Ichimoku Kinko Hyo - (v6.1 - The Convergence Signal Edition)
    --------------------------------------------------------------------------------
    This world-class version evolves into a true quant analysis engine. It introduces
    a dynamic Trend Confidence Score, combining all Ichimoku components into a
    single, actionable metric. This update surgically adds a specialized crossover
    detection between the Tenkan-sen and Senkou Span A, providing a powerful,
    secondary momentum signal for advanced strategies.
    """
    dependencies: list = []

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.tenkan_period = int(self.params.get('tenkan_period', 9))
        self.kijun_period = int(self.params.get('kijun_period', 26))
        self.senkou_b_period = int(self.params.get('senkou_b_period', 52))
        self.chikou_shift = -self.kijun_period # Standard is -26
        self.senkou_lead = self.kijun_period # Standard is 26
        self.timeframe = self.params.get('timeframe', None)

        suffix = f'_{self.tenkan_period}_{self.kijun_period}_{self.senkou_b_period}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        else: suffix += '_base'
        
        self.tenkan_col = f'ichi_tenkan{suffix}'
        self.kijun_col = f'ichi_kijun{suffix}'
        self.chikou_col = f'ichi_chikou{suffix}'
        self.senkou_a_col = f'ichi_senkou_a{suffix}'
        self.senkou_b_col = f'ichi_senkou_b{suffix}'

    def calculate(self) -> 'IchimokuIndicator':
        # --- This function remains unchanged ---
        if len(self.df) < self.senkou_b_period:
            logger.warning(f"Not enough data for Ichimoku on {self.timeframe or 'base'}.")
            for col in [self.tenkan_col, self.kijun_col, self.senkou_a_col, self.senkou_b_col, self.chikou_col]:
                self.df[col] = np.nan
            return self

        tenkan_high = self.df['high'].rolling(window=self.tenkan_period).max()
        tenkan_low = self.df['low'].rolling(window=self.tenkan_period).min()
        self.df[self.tenkan_col] = (tenkan_high + tenkan_low) / 2

        kijun_high = self.df['high'].rolling(window=self.kijun_period).max()
        kijun_low = self.df['low'].rolling(window=self.kijun_period).min()
        self.df[self.kijun_col] = (kijun_high + kijun_low) / 2
        
        self.df[self.senkou_a_col] = ((self.df[self.tenkan_col] + self.df[self.kijun_col]) / 2).shift(self.senkou_lead)

        senkou_b_high = self.df['high'].rolling(window=self.senkou_b_period).max()
        senkou_b_low = self.df['low'].rolling(window=self.senkou_b_period).min()
        self.df[self.senkou_b_col] = ((senkou_b_high + senkou_b_low) / 2).shift(self.senkou_lead)

        self.df[self.chikou_col] = self.df['close'].shift(self.chikou_shift)
        return self

    def analyze(self) -> Dict[str, Any]:
        required_cols = [self.tenkan_col, self.kijun_col, self.senkou_a_col, self.senkou_b_col, 'close']
        empty_analysis = {"values": {}, "analysis": {}}
        if not all(col in self.df.columns for col in required_cols):
            return {"status": "Calculation Incomplete", **empty_analysis}
        
        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 2:
             return {"status": "Insufficient Data", **empty_analysis}

        last, prev = valid_df.iloc[-1], valid_df.iloc[-2]
        
        # --- Component Analysis (Existing logic is untouched) ---
        kumo_top = max(last[self.senkou_a_col], last[self.senkou_b_col])
        kumo_bottom = min(last[self.senkou_a_col], last[self.senkou_b_col])
        price_pos = "Inside Kumo"
        if last['close'] > kumo_top: price_pos = "Above Kumo"
        elif last['close'] < kumo_bottom: price_pos = "Below Kumo"
            
        tk_cross = "Neutral"
        if prev[self.tenkan_col] < prev[self.kijun_col] and last[self.tenkan_col] > last[self.kijun_col]:
            tk_cross = "Weak Bullish" if price_pos == "Below Kumo" else "Strong Bullish"
        elif prev[self.tenkan_col] > prev[self.kijun_col] and last[self.tenkan_col] < last[self.kijun_col]:
            tk_cross = "Weak Bearish" if price_pos == "Above Kumo" else "Strong Bearish"

        future_kumo_dir = "Bullish" if last[self.senkou_a_col] > last[self.senkou_b_col] else "Bearish"
        prev_future_kumo_dir = "Bullish" if prev[self.senkou_a_col] > prev[self.senkou_b_col] else "Bearish"
        kumo_twist = "None"
        if future_kumo_dir == "Bullish" and prev_future_kumo_dir == "Bearish": kumo_twist = "Bullish Twist"
        elif future_kumo_dir == "Bearish" and prev_future_kumo_dir == "Bullish": kumo_twist = "Bearish Twist"

        chikou_status = "Obstructed"
        chikou_price = last.get(self.chikou_col)
        if pd.notna(chikou_price):
            shifted_index = self.df.index.get_loc(last.name) + self.chikou_shift
            if 0 <= shifted_index < len(self.df):
                past_candle = self.df.iloc[shifted_index]
                if pd.notna(past_candle[self.senkou_a_col]) and pd.notna(past_candle[self.senkou_b_col]):
                    past_kumo_top = max(past_candle[self.senkou_a_col], past_candle[self.senkou_b_col])
                    past_kumo_bottom = min(past_candle[self.senkou_a_col], past_candle[self.senkou_b_col])
                    if chikou_price > past_candle['high'] and chikou_price > past_kumo_top: chikou_status = "Free (Bullish)"
                    elif chikou_price < past_candle['low'] and chikou_price < past_kumo_bottom: chikou_status = "Free (Bearish)"

        # ✅ SURGICAL ADDITION v6.1: Tenkan-sen / Senkou Span A Crossover
        tsa_cross = "Neutral"
        if prev[self.tenkan_col] < prev[self.senkou_a_col] and last[self.tenkan_col] > last[self.senkou_a_col]:
            tsa_cross = "Bullish Crossover"
        elif prev[self.tenkan_col] > prev[self.senkou_a_col] and last[self.tenkan_col] < last[self.senkou_a_col]:
            tsa_cross = "Bearish Crossover"

        # --- Dynamic Trend Confidence Score (Existing logic is untouched) ---
        score = 0
        if price_pos == "Above Kumo": score += 3
        elif price_pos == "Below Kumo": score -= 3
        if "Strong Bullish" in tk_cross: score += 2
        elif "Strong Bearish" in tk_cross: score -= 2
        # ... (rest of the scoring logic remains identical)
        if "Weak Bullish" in tk_cross: score += 1
        elif "Weak Bearish" in tk_cross: score -= 1
        if future_kumo_dir == "Bullish": score += 2
        elif future_kumo_dir == "Bearish": score -= 2
        if "Bullish" in chikou_status: score += 3
        elif "Bearish" in chikou_status: score -= 3
        
        trend = "Neutral / Ranging"
        if score >= 5: trend = "Strong Bullish"
        elif score >= 2: trend = "Weak Bullish"
        elif score <= -5: trend = "Strong Bearish"
        elif score <= -2: trend = "Weak Bearish"

        values_content = {
            "tenkan": round(last[self.tenkan_col], 5), "kijun": round(last[self.kijun_col], 5),
            "senkou_a": round(last[self.senkou_a_col], 5), "senkou_b": round(last[self.senkou_b_col], 5),
            "chikou_price": round(chikou_price, 5) if pd.notna(chikou_price) else None
        }
        
        analysis_content = {
            "trend_summary": trend, "trend_score": score,
            "price_position": price_pos, 
            "tk_cross": tk_cross,
            "tsa_cross": tsa_cross, # ✅ ADDED in v6.1: New signal is now part of the output
            "future_kumo_direction": future_kumo_dir,
            "kumo_twist": kumo_twist, 
            "chikou_status": chikou_status
        }
        
        return {
            "status": "OK", "timeframe": self.timeframe or 'Base',
            "values": values_content, "analysis": analysis_content
        }
