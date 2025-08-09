import pandas as pd
import logging
from typing import Dict, Any, Type

# ✨ ۱. ایمپورت کردن تمام اندیکاتورها (قدیمی و جدید)
from .indicators import *

logger = logging.getLogger(__name__)

class IndicatorAnalyzer:
    def __init__(self, df: pd.DataFrame, config: Dict[str, Any] = None):
        if df.empty:
            raise ValueError("Input DataFrame cannot be empty.")
        self.df = df
        self.config = config if config is not None else self._get_default_config()
        
        # ✨ ۲. دیکشنری کامل و جامع از تمام اندیکاتورهای پروژه
        self._indicator_classes: Dict[str, Type[BaseIndicator]] = {
            # قدیمی‌ها
            'rsi': RsiIndicator, 'macd': MacdIndicator, 'bollinger': BollingerIndicator,
            'ichimoku': IchimokuIndicator, 'adx': AdxIndicator, 'supertrend': SuperTrendIndicator,
            'obv': ObvIndicator, 'stochastic': StochasticIndicator, 'cci': CciIndicator,
            'mfi': MfiIndicator, 'atr': AtrIndicator, 'patterns': PatternIndicator,
            'divergence': DivergenceIndicator, 'pivots': PivotPointIndicator,
            'structure': StructureIndicator, 'whales': WhaleIndicator,
            # جدیدها
            'ema_cross': EMACrossIndicator,
            'vwap_bands': VwapBandsIndicator,
            'chandelier_exit': ChandelierExitIndicator,
            'donchian_channel': DonchianChannelIndicator,
            'fast_ma': FastMAIndicator,
            'williams_r': WilliamsRIndicator,
            'keltner_channel': KeltnerChannelIndicator,
            'zigzag': ZigzagIndicator,
            'fibonacci': FibonacciIndicator,
        }
        self._indicator_instances: Dict[str, BaseIndicator] = {}

    def _get_default_config(self) -> Dict[str, Any]:
        # ✨ ۳. اضافه کردن کانفیگ پیش‌فرض برای اندیکاتورهای جدید
        default_config = {
            'rsi': {'period': 14, 'enabled': True},
            'macd': {'fast_period': 12, 'slow_period': 26, 'signal_period': 9, 'enabled': True},
            'bollinger': {'period': 20, 'std_dev': 2, 'enabled': True},
            'ichimoku': {'enabled': True}, 'adx': {'period': 14, 'enabled': True},
            'supertrend': {'period': 10, 'multiplier': 3.0, 'enabled': True},
            'obv': {'enabled': True}, 'stochastic': {'k_period': 14, 'd_period': 3, 'enabled': True},
            'cci': {'period': 20, 'enabled': True}, 'mfi': {'period': 14, 'enabled': True},
            'atr': {'period': 14, 'enabled': True}, 'patterns': {'enabled': True},
            'divergence': {'enabled': True}, 'pivots': {'enabled': True},
            'structure': {'sensitivity': 7, 'enabled': True}, 'whales': {'spike_multiplier': 3.5, 'enabled': True},
            # --- کانفیگ جدید ---
            'ema_cross': {'short_period': 9, 'long_period': 21, 'enabled': False},
            'vwap_bands': {'std_dev_multiplier': 2.0, 'enabled': False},
            'chandelier_exit': {'atr_period': 22, 'atr_multiplier': 3.0, 'enabled': False},
            'donchian_channel': {'period': 20, 'enabled': False},
            'fast_ma': {'period': 50, 'ma_type': 'DEMA', 'enabled': False},
            'williams_r': {'period': 14, 'enabled': False},
            'keltner_channel': {'ema_period': 20, 'atr_multiplier': 2.0, 'enabled': False},
            'zigzag': {'deviation': 5.0, 'enabled': False},
            'fibonacci': {'zigzag_deviation': 5.0, 'enabled': False},
        }
        return default_config

    def calculate_all(self) -> pd.DataFrame:
        # این متد به لطف استانداردسازی، دیگر نیازی به تغییر ندارد و به درستی کار می‌کند
        logger.info("Starting calculation for all enabled indicators.")
        for name, params in self.config.items():
            if params.get('enabled', False):
                indicator_class = self._indicator_classes.get(name)
                if indicator_class:
                    try:
                        instance = indicator_class(self.df, **params)
                        self.df = instance.calculate()
                        self._indicator_instances[name] = instance
                    except Exception as e:
                        logger.error(f"Failed to calculate indicator '{name}': {e}", exc_info=True)
        return self.df

    def get_analysis_summary(self) -> Dict[str, Any]:
        # ✨ ۴. ارتقا: اضافه کردن قیمت کندل قبلی برای استراتژی‌ها
        summary: Dict[str, Any] = {}
        if len(self.df) > 0:
            last_row = self.df.iloc[-1]
            summary['price_data'] = {'open': last_row.get('open'),'high': last_row.get('high'),'low': last_row.get('low'),'close': last_row.get('close'),'volume': last_row.get('volume')}
        if len(self.df) > 1:
            prev_row = self.df.iloc[-2]
            summary['price_data_prev'] = {'close': prev_row.get('close')}

        for name, instance in self._indicator_instances.items():
            try:
                analysis = instance.analyze()
                if analysis: summary[name] = analysis
            except Exception as e:
                logger.error(f"Failed to analyze indicator '{name}': {e}", exc_info=True)
                summary[name] = {"error": str(e)}
        return summary
