# engines/indicator_analyzer.py (نسخه جدید و جهانی - مبتنی بر معماری ماژولار)

import pandas as pd
import logging
from typing import Dict, Any, Type, List

# --- وارد کردن کلاس‌های اندیکاتور مستقل از پکیج جدید ---
from .indicators import BaseIndicator, RsiIndicator, MacdIndicator

# به محض ساخت هر اندیکاتور جدید، آن را در بالا import خواهیم کرد
# from .indicators.bollinger import BollingerIndicator
# from .indicators.ichimoku import IchimokuIndicator

logger = logging.getLogger(__name__)

class IndicatorAnalyzer:
    """
    ارکستریتور اندیکاتورهای تکنیکال.
    
    این کلاس به عنوان "ستاد فرماندهی" عمل می‌کند. وظیفه آن مدیریت، اجرا
    و جمع‌آوری نتایج از تمام ماژول‌های اندیکاتور ثبت‌شده است. این کلاس
    دیگر منطق محاسباتی اندیکاتورها را در خود ندارد و فقط آن‌ها را مدیریت می‌کند.
    """
    
    def __init__(self, df: pd.DataFrame, config: Dict[str, Any] = None):
        """
        سازنده کلاس.

        Args:
            df (pd.DataFrame): دیتافریم اصلی کندل‌ها (OHLCV).
            config (Dict[str, Any], optional): تنظیمات سفارشی برای اجرای اندیکاتورها.
        """
        self.df = df
        self.config = config if config is not None else self._get_default_config()
        
        # دیکشنری برای نگهداری کلاس‌های اندیکاتور برای دسترسی آسان
        self._indicator_classes: Dict[str, Type[BaseIndicator]] = {
            'rsi': RsiIndicator,
            'macd': MacdIndicator,
            # 'bollinger': BollingerIndicator, # در آینده اضافه می‌شود
            # 'ichimoku': IchimokuIndicator,   # در آینده اضافه می‌شود
        }
        
        self.calculated_indicators: List[str] = []

    def _get_default_config(self) -> Dict[str, Any]:
        """تنظیمات پیش‌فرض برای هر اندیکاتور را برمی‌گرداند."""
        return {
            'rsi': {'period': 14, 'enabled': True},
            'macd': {'fast_period': 12, 'slow_period': 26, 'signal_period': 9, 'enabled': True},
            # 'bollinger': {'period': 20, 'std_dev': 2, 'enabled': True},
        }

    def calculate_all(self) -> pd.DataFrame:
        """
        تمام اندیکاتورهای فعال در کانفیگ را به ترتیب محاسبه می‌کند.
        این متد از طریق حلقه روی تنظیمات، نمونه‌های لازم از کلاس‌های اندیکاتور
        را ساخته و متد calculate() آن‌ها را فراخوانی می‌کند.
        """
        logger.info("Starting calculation for all enabled indicators based on config.")
        
        for name, params in self.config.items():
            if params.get('enabled', False):
                indicator_class = self._indicator_classes.get(name)
                if indicator_class:
                    try:
                        # ساخت نمونه از کلاس اندیکاتور با پارامترهای مشخص شده
                        indicator_instance = indicator_class(self.df, **params)
                        # اجرای محاسبه
                        self.df = indicator_instance.calculate()
                        self.calculated_indicators.append(name)
                        logger.debug(f"Successfully calculated indicator: {name}")
                    except Exception as e:
                        logger.error(f"Failed to calculate indicator '{name}': {e}", exc_info=True)
                else:
                    logger.warning(f"Indicator class for '{name}' not found in _indicator_classes.")
                    
        return self.df

    def get_analysis_summary(self) -> Dict[str, Any]:
        """
        برای تمام اندیکاتورهای محاسبه‌شده، تحلیل هوشمند آن‌ها را دریافت کرده
        و در یک دیکشنری جامع و استاندارد جمع‌آوری می‌کند.
        
        این متد، "مغز تحلیلی" این کلاس است.
        """
        logger.info("Generating analysis summary from calculated indicators.")
        summary: Dict[str, Any] = {}
        
        for name in self.calculated_indicators:
            indicator_class = self._indicator_classes.get(name)
            if indicator_class:
                try:
                    params = self.config.get(name, {})
                    indicator_instance = indicator_class(self.df, **params)
                    # دریافت تحلیل (مقدار + سیگنال) از هر اندیکاتور
                    summary[name] = indicator_instance.analyze()
                except Exception as e:
                    logger.error(f"Failed to analyze indicator '{name}': {e}", exc_info=True)
                    summary[name] = {"error": str(e)}

        return summary
