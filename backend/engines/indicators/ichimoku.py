# engines/indicators/ichimoku.py

import pandas as pd
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class IchimokuIndicator(BaseIndicator):
    """
    کلاس محاسبه و تحلیل جامع و حرفه‌ای سیستم معاملاتی Ichimoku Kinko Hyo.

    این ماژول تمام پنج مولفه ایچیموکو را محاسبه کرده و روابط بین آن‌ها را برای
    تولید سیگنال‌های معاملاتی دقیق و مبتنی بر زمینه (Context-Aware) تحلیل می‌کند.
    """

    def __init__(self, df: pd.DataFrame, tenkan_period: int = 9, kijun_period: int = 26, senkou_b_period: int = 52, chikou_lag: int = -26, senkou_lead: int = 26):
        super().__init__(df, tenkan_period=tenkan_period, kijun_period=kijun_period, senkou_b_period=senkou_b_period)
        self.tenkan_period = tenkan_period
        self.kijun_period = kijun_period
        self.senkou_b_period = senkou_b_period
        self.chikou_lag = chikou_lag  # باید منفی باشد تا به گذشته شیفت دهد
        self.senkou_lead = senkou_lead # باید مثبت باشد تا به آینده شیفت دهد

    def calculate(self) -> pd.DataFrame:
        """محاسبه تمام پنج خط اصلی سیستم ایچیموکو."""
        
        # ۱. تنکان سن (Tenkan-sen)
        high_tenkan = self.df['high'].rolling(window=self.tenkan_period).max()
        low_tenkan = self.df['low'].rolling(window=self.tenkan_period).min()
        self.df['tenkan_sen'] = (high_tenkan + low_tenkan) / 2

        # ۲. کیجون سن (Kijun-sen)
        high_kijun = self.df['high'].rolling(window=self.kijun_period).max()
        low_kijun = self.df['low'].rolling(window=self.kijun_period).min()
        self.df['kijun_sen'] = (high_kijun + low_kijun) / 2

        # ۳. چیکو اسپن (Chikou Span) - شیفت قیمت به گذشته
        self.df['chikou_span'] = self.df['close'].shift(self.chikou_lag)

        # ۴. سنکو اسپن A (Senkou Span A) - شیفت به آینده
        self.df['senkou_span_a'] = ((self.df['tenkan_sen'] + self.df['kijun_sen']) / 2).shift(self.senkou_lead)

        # ۵. سنکو اسپن B (Senkou Span B) - شیفت به آینده
        high_senkou_b = self.df['high'].rolling(window=self.senkou_b_period).max()
        low_senkou_b = self.df['low'].rolling(window=self.senkou_b_period).min()
        self.df['senkou_span_b'] = ((high_senkou_b + low_senkou_b) / 2).shift(self.senkou_lead)
        
        logger.debug("Calculated all 5 Ichimoku components successfully.")
        return self.df

    def analyze(self) -> dict:
        """
        تحلیل جامع روابط بین مولفه‌های ایچیموکو و تولید یک سیگنال ترکیبی.
        این متد سیگنال‌ها را اولویت‌بندی می‌کند (مثلاً شکست کومو مهم‌تر از کراس TK است).
        """
        required_cols = ['tenkan_sen', 'kijun_sen', 'chikou_span', 'senkou_span_a', 'senkou_span_b']
        if not all(col in self.df.columns and not self.df[col].isnull().all() for col in required_cols):
            raise ValueError("Ichimoku columns not found or are all NaN. Please run calculate() first.")

        # استخراج آخرین داده‌های موجود
        last = self.df.iloc[-1]
        prev = self.df.iloc[-2]
        
        # داده‌های مربوط به ۲۶ دوره قبل برای مقایسه با چیکو اسپن
        past_26 = self.df.iloc[-1 - self.senkou_lead]

        # --- ۱. تحلیل موقعیت نسبت به ابر (کومو) ---
        kumo_top = max(last['senkou_span_a'], last['senkou_span_b'])
        kumo_bottom = min(last['senkou_span_a'], last['senkou_span_b'])
        
        price_status = "Inside Kumo"
        if last['close'] > kumo_top:
            price_status = "Above Kumo"
        elif last['close'] < kumo_bottom:
            price_status = "Below Kumo"
            
        # --- ۲. تحلیل کراس تنکان/کیجون (TK Cross) ---
        tk_cross_signal = "Neutral"
        if prev['tenkan_sen'] < prev['kijun_sen'] and last['tenkan_sen'] > last['kijun_sen']:
            # کراس صعودی. حالا قدرت آن را بر اساس موقعیت ابر تعیین می‌کنیم.
            if price_status == "Above Kumo": tk_cross_signal = "Strong Bullish TK Cross"
            elif price_status == "Inside Kumo": tk_cross_signal = "Neutral Bullish TK Cross"
            else: tk_cross_signal = "Weak Bullish TK Cross"
        elif prev['tenkan_sen'] > prev['kijun_sen'] and last['tenkan_sen'] < last['kijun_sen']:
            # کراس نزولی
            if price_status == "Below Kumo": tk_cross_signal = "Strong Bearish TK Cross"
            elif price_status == "Inside Kumo": tk_cross_signal = "Neutral Bearish TK Cross"
            else: tk_cross_signal = "Weak Bearish TK Cross"

        # --- ۳. تحلیل تایید چیکو اسپن ---
        chikou_confirmation = "Neutral"
        if last['chikou_span'] > past_26['high']:
            chikou_confirmation = "Bullish Confirmation"
        elif last['chikou_span'] < past_26['low']:
            chikou_confirmation = "Bearish Confirmation"
            
        # --- ۴. اولویت‌بندی و تولید سیگنال نهایی ---
        final_signal = tk_cross_signal  # سیگنال پیش‌فرض، کراس TK است

        # سیگنال شکست کومو، تمام سیگنال‌های دیگر را بازنویسی می‌کند
        prev_price_status = "Inside Kumo"
        prev_kumo_top = max(prev['senkou_span_a'], prev['senkou_span_b'])
        prev_kumo_bottom = min(prev['senkou_span_a'], prev['senkou_span_b'])
        if prev['close'] > prev_kumo_top: prev_price_status = "Above Kumo"
        elif prev['close'] < prev_kumo_bottom: prev_price_status = "Below Kumo"
        
        if prev_price_status != "Above Kumo" and price_status == "Above Kumo" and chikou_confirmation == "Bullish Confirmation":
            final_signal = "Bullish Kumo Breakout"
        elif prev_price_status != "Below Kumo" and price_status == "Below Kumo" and chikou_confirmation == "Bearish Confirmation":
            final_signal = "Bearish Kumo Breakout"

        return {
            "tenkan_sen": round(last['tenkan_sen'], 5),
            "kijun_sen": round(last['kijun_sen'], 5),
            "chikou_span": round(last['chikou_span'], 5),
            "senkou_span_a": round(last['senkou_span_a'], 5),
            "senkou_span_b": round(last['senkou_span_b'], 5),
            "price_position": price_status,
            "chikou_confirmation": chikou_confirmation,
            "signal": final_signal
        }
