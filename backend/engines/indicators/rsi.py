# engines/indicators/rsi.py

import pandas as pd
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class RsiIndicator(BaseIndicator):
    """
    کلاس محاسبه و تحلیل اندیکاتور Relative Strength Index (RSI).
    این کلاس از BaseIndicator ارث‌بری کرده و متدهای calculate و analyze را پیاده‌سازی می‌کند.
    """
    
    def __init__(self, df: pd.DataFrame, period: int = 14):
        """
        سازنده کلاس RSI.
        
        Args:
            df (pd.DataFrame): دیتافریم OHLCV.
            period (int): دوره زمانی برای محاسبه RSI (پیش‌فرض ۱۴).
        """
        super().__init__(df, period=period)
        self.column_name = f'rsi_{period}'

    def calculate(self) -> pd.DataFrame:
        """
        RSI را با استفاده از میانگین متحرک نمایی (EMA) محاسبه می‌کند که روشی مدرن‌تر
        و دقیق‌تر نسبت به میانگین متحرک ساده (SMA) است و در پلتفرم‌هایی مانند TradingView استفاده می‌شود.
        """
        period = self.params.get('period', 14)
        
        # محاسبه تغییرات قیمت
        delta = self.df['close'].diff()
        
        # جدا کردن سودها و زیان‌ها
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        # محاسبه میانگین نمایی سود و زیان
        avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
        
        # محاسبه RS و سپس RSI
        # افزودن مقدار کوچک 1e-12 برای جلوگیری از خطای تقسیم بر صفر در بازارهای بدون نوسان
        rs = avg_gain / (avg_loss + 1e-12)
        self.df[self.column_name] = 100.0 - (100.0 / (1.0 + rs))
        
        logger.debug(f"Calculated {self.column_name} successfully.")
        return self.df

    def analyze(self) -> dict:
        """
        آخرین مقدار RSI را تحلیل کرده و وضعیت اشباع خرید/فروش یا خنثی را مشخص می‌کند.
        """
        if self.column_name not in self.df.columns:
            raise ValueError(f"RSI column '{self.column_name}' not found. Please run calculate() first.")
            
        last_rsi = self.df[self.column_name].iloc[-1]
        
        signal = "Neutral"
        # تحلیل بر اساس سطوح استاندارد RSI
        if last_rsi > 70:
            signal = "Overbought"
        elif last_rsi < 30:
            signal = "Oversold"
            
        return {
            "value": round(last_rsi, 2),
            "signal": signal
        }
