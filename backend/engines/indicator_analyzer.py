# engines/indicator_analyzer.py (نهایی با ATR)

import pandas as pd
import logging
from typing import Dict, Any, Type, List

# --- ایمپورت کلاس AtrIndicator ---
from .indicators import (
    BaseIndicator, RsiIndicator, MacdIndicator, BollingerIndicator, 
    IchimokuIndicator, AdxIndicator, SuperTrendIndicator, ObvIndicator,
    StochasticIndicator, CciIndicator, MfiIndicator, AtrIndicator
)

logger = logging.getLogger(__name__)

class IndicatorAnalyzer:
    def __init__(self, df: pd.DataFrame, config: Dict[str, Any] = None):
        self.df = df
        self.config = config if config is not None else self._get_default_config()
        
        # --- افزودن AtrIndicator به دیکشنری کلاس‌ها ---
        self._indicator_classes: Dict[str, Type[BaseIndicator]] = {
            'rsi': RsiIndicator,
            'macd': MacdIndicator,
            'bollinger': BollingerIndicator,
            'ichimoku': IchimokuIndicator,
            'adx': AdxIndicator,
            'supertrend': SuperTrendIndicator,
            'obv': ObvIndicator,
            'stochastic': StochasticIndicator,
            'cci': CciIndicator,
            'mfi': MfiIndicator,
            'atr': AtrIndicator,
        }
        
        self.calculated_indicators: List[str] = []

    def _get_default_config(self) -> Dict[str, Any]:
        """تنظیمات پیش‌فرض برای هر اندیکاتور را برمی‌گرداند."""
        return {
            'rsi': {'period': 14, 'enabled': True},
            'macd': {'fast_period': 12, 'slow_period': 26, 'signal_period': 9, 'enabled': True},
            'bollinger': {'period': 20, 'std_dev': 2, 'enabled': True},
            'ichimoku': {'tenkan_period': 9, 'kijun_period': 26, 'senkou_b_period': 52, 'enabled': True},
            'adx': {'period': 14, 'enabled': True},
            'supertrend': {'period': 10, 'multiplier': 3.0, 'enabled': True},
            'obv': {'ma_period': 20, 'enabled': True},
            'stochastic': {'k_period': 14, 'd_period': 3, 'smooth_k': 3, 'enabled': True},
            'cci': {'period': 20, 'constant': 0.015, 'enabled': True},
            'mfi': {'period': 14, 'enabled': True},
            # --- افزودن کانفیگ پیش‌فرض برای ATR ---
            'atr': {'period': 14, 'enabled': True},
        }

    # متدهای calculate_all و get_analysis_summary بدون هیچ تغییری باقی می‌مانند
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
