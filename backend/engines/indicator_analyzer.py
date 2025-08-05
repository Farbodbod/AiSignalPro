# engines/indicator_analyzer.py (نسخه نهایی با پشتیبانی از بولینگر بندز)

import pandas as pd
import logging
from typing import Dict, Any, Type, List

# --- ۱. ایمپورت کلاس جدید ---
from .indicators import BaseIndicator, RsiIndicator, MacdIndicator, BollingerIndicator

logger = logging.getLogger(__name__)

class IndicatorAnalyzer:
    def __init__(self, df: pd.DataFrame, config: Dict[str, Any] = None):
        self.df = df
        self.config = config if config is not None else self._get_default_config()
        
        # --- ۲. افزودن کلاس به دیکشنری ---
        self._indicator_classes: Dict[str, Type[BaseIndicator]] = {
            'rsi': RsiIndicator,
            'macd': MacdIndicator,
            'bollinger': BollingerIndicator, 
        }
        
        self.calculated_indicators: List[str] = []

    def _get_default_config(self) -> Dict[str, Any]:
        """تنظیمات پیش‌فرض برای هر اندیکاتور را برمی‌گرداند."""
        return {
            'rsi': {'period': 14, 'enabled': True},
            'macd': {'fast_period': 12, 'slow_period': 26, 'signal_period': 9, 'enabled': True},
            # --- ۳. افزودن کانفیگ پیش‌فرض ---
            'bollinger': {'period': 20, 'std_dev': 2, 'enabled': True},
        }

    def calculate_all(self) -> pd.DataFrame:
        logger.info("Starting calculation for all enabled indicators based on config.")
        for name, params in self.config.items():
            if params.get('enabled', False):
                indicator_class = self._indicator_classes.get(name)
                if indicator_class:
                    try:
                        indicator_instance = indicator_class(self.df, **params)
                        self.df = indicator_instance.calculate()
                        self.calculated_indicators.append(name)
                        logger.debug(f"Successfully calculated indicator: {name}")
                    except Exception as e:
                        logger.error(f"Failed to calculate indicator '{name}': {e}", exc_info=True)
                else:
                    logger.warning(f"Indicator class for '{name}' not found in _indicator_classes.")
        return self.df

    def get_analysis_summary(self) -> Dict[str, Any]:
        logger.info("Generating analysis summary from calculated indicators.")
        summary: Dict[str, Any] = {}
        for name in self.calculated_indicators:
            indicator_class = self._indicator_classes.get(name)
            if indicator_class:
                try:
                    params = self.config.get(name, {})
                    indicator_instance = indicator_class(self.df, **params)
                    summary[name] = indicator_instance.analyze()
                except Exception as e:
                    logger.error(f"Failed to analyze indicator '{name}': {e}", exc_info=True)
                    summary[name] = {"error": str(e)}
        return summary
