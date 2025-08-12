import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

from .base import BaseIndicator

logger = logging.getLogger(__name__)

class IchimokuIndicator(BaseIndicator):
    """
    Ichimoku Kinko Hyo - (v5.0 - Miracle Edition)
    --------------------------------------------------------------------------------
    This world-class version is a true analysis engine. It not only calculates the
    core Ichimoku lines but also provides deep contextual analysis, including the
    critical "Kumo Twist" for future trend prediction and "Chikou Span Freedom"
    for current trend validation, empowering the most advanced strategies.
    """
    dependencies: list = []

    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.params = kwargs.get('params', {})
        self.tenkan_period = int(self.params.get('tenkan_period', 9))
        self.kijun_period = int(self.params.get('kijun_period', 26))
        self.senkou_b_period = int(self.params.get('senkou_b_period', 52))
        self.chikou_shift = -self.tenkan_period # Common setting for more responsive SL
        self.senkou_lead = self.kijun_period
        self.timeframe = self.params.get('timeframe', None)

        suffix = f'_{self.tenkan_period}_{self.kijun_period}_{self.senkou_b_period}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        self.tenkan_col = f'ichi_tenkan{suffix}'
        self.kijun_col = f'ichi_kijun{suffix}'
        self.chikou_col = f'ichi_chikou{suffix}'
        self.senkou_a_col = f'ichi_senkou_a{suffix}'
        self.senkou_b_col = f'ichi_senkou_b{suffix}'

    def calculate(self) -> 'IchimokuIndicator':
        """
        Calculates all five Ichimoku lines. The core calculation logic remains
        unchanged as it is the mathematical standard.
        """
        df_for_calc = self.df
        
        if len(df_for_calc) < self.senkou_b_period:
            logger.warning(f"Not enough data for Ichimoku on timeframe {self.timeframe or 'base'}.")
            for col in [self.tenkan_col, self.kijun_col, self.senkou_a_col, self.senkou_b_col, self.chikou_col]:
                self.df[col] = np.nan
            return self

        # Core Line Calculations
        tenkan_high = df_for_calc['high'].rolling(window=self.tenkan_period).max()
        tenkan_low = df_for_calc['low'].rolling(window=self.tenkan_period).min()
        self.df[self.tenkan_col] = (tenkan_high + tenkan_low) / 2

        kijun_high = df_for_calc['high'].rolling(window=self.kijun_period).max()
        kijun_low = df_for_calc['low'].rolling(window=self.kijun_period).min()
        self.df[self.kijun_col] = (kijun_high + kijun_low) / 2
        
        senkou_b_high = df_for_calc['high'].rolling(window=self.senkou_b_period).max()
        senkou_b_low = df_for_calc['low'].rolling(window=self.senkou_b_period).min()
        self.df[self.senkou_b_col] = ((senkou_b_high + senkou_b_low) / 2).shift(self.senkou_lead)

        self.df[self.senkou_a_col] = ((self.df[self.tenkan_col] + self.df[self.kijun_col]) / 2).shift(self.senkou_lead)

        self.df[self.chikou_col] = df_for_calc['close'].shift(self.chikou_shift)

        return self

    def analyze(self) -> Dict[str, Any]:
        """
        The new, powerful analysis engine providing deep contextual insights.
        """
        required_cols = [self.tenkan_col, self.kijun_col, self.senkou_a_col, self.senkou_b_col]
        valid_df = self.df.dropna(subset=required_cols)
        
        if len(valid_df) < 2:
             return {"status": "Insufficient Data", "analysis": {}}

        last = valid_df.iloc[-1]
        prev = valid_df.iloc[-2]

        # --- 1. Price Position vs. Kumo ---
        kumo_top = max(last[self.senkou_a_col], last[self.senkou_b_col])
        kumo_bottom = min(last[self.senkou_a_col], last[self.senkou_b_col])
        price_pos = "Inside Kumo"
        if last['close'] > kumo_top: price_pos = "Above Kumo"
        elif last['close'] < kumo_bottom: price_pos = "Below Kumo"
            
        # --- 2. Tenkan/Kijun (TK) Cross Analysis ---
        tk_cross = "Neutral"
        if prev[self.tenkan_col] < prev[self.kijun_col] and last[self.tenkan_col] > last[self.kijun_col]:
            tk_cross = "Weak Bullish" if price_pos == "Below Kumo" else "Strong Bullish"
        elif prev[self.tenkan_col] > prev[self.kijun_col] and last[self.tenkan_col] < last[self.kijun_col]:
            tk_cross = "Weak Bearish" if price_pos == "Above Kumo" else "Strong Bearish"

        # --- ✅ 3. Kumo Twist Analysis (New Feature) ---
        future_kumo_dir = "Bullish" if last[self.senkou_a_col] > last[self.senkou_b_col] else "Bearish"
        prev_future_kumo_dir = "Bullish" if prev[self.senkou_a_col] > prev[self.senkou_b_col] else "Bearish"
        kumo_twist = "None"
        if future_kumo_dir == "Bullish" and prev_future_kumo_dir == "Bearish":
            kumo_twist = "Bullish Twist"
        elif future_kumo_dir == "Bearish" and prev_future_kumo_dir == "Bullish":
            kumo_twist = "Bearish Twist"

        # --- ✅ 4. Chikou Span Freedom Analysis (New Feature) ---
        chikou_status = "Obstructed"
        chikou_price = last.get(self.chikou_col) # This is the close price from 26 periods ago
        
        if pd.notna(chikou_price):
            past_candle_index = valid_df.index.get_loc(last.name) + self.chikou_shift
            if past_candle_index >= 0 and past_candle_index < len(valid_df):
                past_candle = valid_df.iloc[past_candle_index]
                past_kumo_top = max(past_candle[self.senkou_a_col], past_candle[self.senkou_b_col])
                past_kumo_bottom = min(past_candle[self.senkou_a_col], past_candle[self.senkou_b_col])
                
                if chikou_price > past_candle['high'] and chikou_price > past_kumo_top:
                    chikou_status = "Free (Bullish)"
                elif chikou_price < past_candle['low'] and chikou_price < past_kumo_bottom:
                    chikou_status = "Free (Bearish)"
                elif chikou_price > past_kumo_top:
                    chikou_status = "Obstructed by Price"
                elif chikou_price < past_kumo_bottom:
                    chikou_status = "Obstructed by Price"
                else:
                    chikou_status = "Obstructed by Kumo"

        # --- 5. Final Trend Summary ---
        trend = "Neutral / Ranging"
        if price_pos == "Above Kumo" and future_kumo_dir == "Bullish" and chikou_status == "Free (Bullish)":
            trend = "Confirmed Bullish Trend"
        elif price_pos == "Below Kumo" and future_kumo_dir == "Bearish" and chikou_status == "Free (Bearish)":
            trend = "Confirmed Bearish Trend"
        elif price_pos == "Above Kumo": trend = "Weak Bullish"
        elif price_pos == "Below Kumo": trend = "Weak Bearish"
        
        return {
            "status": "OK",
            "timeframe": self.timeframe or 'Base',
            "values": {
                "tenkan": round(last[self.tenkan_col], 5),
                "kijun": round(last[self.kijun_col], 5),
                "senkou_a": round(last[self.senkou_a_col], 5),
                "senkou_b": round(last[self.senkou_b_col], 5),
                "chikou_price": round(chikou_price, 5) if pd.notna(chikou_price) else None
            },
            "analysis": {
                "trend_summary": trend,
                "price_position": price_pos,
                "tk_cross": tk_cross,
                "future_kumo_direction": future_kumo_dir,
                "kumo_twist": kumo_twist,
                "chikou_status": chikou_status
            }
        }

