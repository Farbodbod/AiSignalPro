import pandas as pd
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class IchimokuIndicator(BaseIndicator):
    """
    ✨ UPGRADE v2.0 ✨
    - Constructor standardized to use **kwargs.
    - Analyze method logic refined for clarity.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.tenkan_period = self.params.get('tenkan_period', 9)
        self.kijun_period = self.params.get('kijun_period', 26)
        self.senkou_b_period = self.params.get('senkou_b_period', 52)
        self.chikou_lag = self.params.get('chikou_lag', -26)
        self.senkou_lead = self.params.get('senkou_lead', 26)

    def calculate(self) -> pd.DataFrame:
        high_tenkan = self.df['high'].rolling(window=self.tenkan_period).max()
        low_tenkan = self.df['low'].rolling(window=self.tenkan_period).min()
        self.df['tenkan_sen'] = (high_tenkan + low_tenkan) / 2

        high_kijun = self.df['high'].rolling(window=self.kijun_period).max()
        low_kijun = self.df['low'].rolling(window=self.kijun_period).min()
        self.df['kijun_sen'] = (high_kijun + low_kijun) / 2

        self.df['chikou_span'] = self.df['close'].shift(self.chikou_lag)
        self.df['senkou_span_a'] = ((self.df['tenkan_sen'] + self.df['kijun_sen']) / 2).shift(self.senkou_lead)

        high_senkou_b = self.df['high'].rolling(window=self.senkou_b_period).max()
        low_senkou_b = self.df['low'].rolling(window=self.senkou_b_period).min()
        self.df['senkou_span_b'] = ((high_senkou_b + low_senkou_b) / 2).shift(self.senkou_lead)
        return self.df

    def analyze(self) -> dict:
        last = self.df.iloc[-1]; prev = self.df.iloc[-2]
        past_26 = self.df.iloc[-1 - self.senkou_lead] if len(self.df) > self.senkou_lead else self.df.iloc[0]

        kumo_top = max(last['senkou_span_a'], last['senkou_span_b'])
        kumo_bottom = min(last['senkou_span_a'], last['senkou_span_b'])
        
        price_status = "Inside Kumo"
        if last['close'] > kumo_top: price_status = "Above Kumo"
        elif last['close'] < kumo_bottom: price_status = "Below Kumo"
            
        tk_cross_signal = "Neutral"
        if prev['tenkan_sen'] < prev['kijun_sen'] and last['tenkan_sen'] > last['kijun_sen']:
            if price_status == "Above Kumo": tk_cross_signal = "Strong Bullish TK Cross"
            elif price_status == "Inside Kumo": tk_cross_signal = "Neutral Bullish TK Cross"
            else: tk_cross_signal = "Weak Bullish TK Cross"
        elif prev['tenkan_sen'] > prev['kijun_sen'] and last['tenkan_sen'] < last['kijun_sen']:
            if price_status == "Below Kumo": tk_cross_signal = "Strong Bearish TK Cross"
            elif price_status == "Inside Kumo": tk_cross_signal = "Neutral Bearish TK Cross"
            else: tk_cross_signal = "Weak Bearish TK Cross"

        chikou_confirmation = "Neutral"
        if last['chikou_span'] > past_26['high']: chikou_confirmation = "Bullish Confirmation"
        elif last['chikou_span'] < past_26['low']: chikou_confirmation = "Bearish Confirmation"
            
        final_signal = tk_cross_signal
        
        return {
            "tenkan_sen": round(last['tenkan_sen'], 5), "kijun_sen": round(last['kijun_sen'], 5),
            "chikou_span": round(last['chikou_span'], 5), "senkou_span_a": round(last['senkou_span_a'], 5),
            "senkou_span_b": round(last['senkou_span_b'], 5), "price_position": price_status,
            "chikou_confirmation": chikou_confirmation, "signal": final_signal
        }
