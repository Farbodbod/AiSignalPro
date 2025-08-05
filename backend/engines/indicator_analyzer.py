# engines/indicator_analyzer.py

import pandas as pd
import logging
from typing import Dict, Any, Type, List

from .indicators import (
    BaseIndicator, RsiIndicator, MacdIndicator, BollingerIndicator, 
    IchimokuIndicator, AdxIndicator, SuperTrendIndicator, ObvIndicator,
    StochasticIndicator, CciIndicator, MfiIndicator, AtrIndicator,
    PatternIndicator, DivergenceIndicator, PivotPointIndicator, 
    StructureIndicator, WhaleIndicator # <--- کلاس جدید
)

logger = logging.getLogger(__name__)

class IndicatorAnalyzer:
    def __init__(self, df: pd.DataFrame, config: Dict[str, Any] = None):
        self.df = df
        self.config = config if config is not None else self._get_default_config()
        self._indicator_classes: Dict[str, Type[BaseIndicator]] = {
            'rsi': RsiIndicator, 'macd': MacdIndicator, 'bollinger': BollingerIndicator,
            'ichimoku': IchimokuIndicator, 'adx': AdxIndicator, 'supertrend': SuperTrendIndicator,
            'obv': ObvIndicator, 'stochastic': StochasticIndicator, 'cci': CciIndicator,
            'mfi': MfiIndicator, 'atr': AtrIndicator, 'patterns': PatternIndicator,
            'divergence': DivergenceIndicator, 'pivots': PivotPointIndicator,
            'structure': StructureIndicator, 'whales': WhaleIndicator, # <--- ماژول جدید
        }
        self.calculated_indicators: List[str] = []

    def _get_default_config(self) -> Dict[str, Any]:
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
            'atr': {'period': 14, 'enabled': True},
            'patterns': {'enabled': True},
            'divergence': {'period': 14, 'lookback': 30, 'enabled': True},
            'pivots': {'method': 'standard', 'enabled': True},
            'structure': {'sensitivity': 7, 'enabled': True},
            'whales': {'period': 20, 'spike_multiplier': 3.5, 'enabled': True}, # <--- کانفیگ جدید
        }

    def calculate_all(self) -> pd.DataFrame:
        # ... (کد این متد بدون تغییر باقی می‌ماند)
        logger.info("Starting calculation for all enabled indicators based on config.")
        for name, params in self.config.items():
            if params.get('enabled', False):
                indicator_class = self._indicator_classes.get(name)
                if indicator_class:
                    try:
                        init_params = params.copy()
                        init_params.pop('enabled', None)
                        indicator_instance = indicator_class(self.df, **init_params)
                        self.df = indicator_instance.calculate()
                        self.calculated_indicators.append(name)
                        logger.debug(f"Successfully calculated indicator: {name}")
                    except Exception as e:
                        logger.error(f"Failed to calculate indicator '{name}': {e}", exc_info=True)
                else:
                    logger.warning(f"Indicator class for '{name}' not found in _indicator_classes.")
        return self.df

    def get_analysis_summary(self) -> Dict[str, Any]:
        # ... (کد این متد بدون تغییر باقی می‌ماند)
        logger.info("Generating analysis summary from calculated indicators.")
        summary: Dict[str, Any] = {}
        if not self.df.empty:
            last_price_row = self.df.iloc[-1]
            summary['price_data'] = { 'open': last_price_row.get('open'), 'high': last_price_row.get('high'), 'low': last_price_row.get('low'), 'close': last_price_row.get('close'), 'volume': last_price_row.get('volume'), }
        for name in self.calculated_indicators:
            indicator_class = self._indicator_classes.get(name)
            if indicator_class:
                try:
                    init_params = self.config.get(name, {}).copy()
                    init_params.pop('enabled', None)
                    indicator_instance = indicator_class(self.df, **init_params)
                    summary[name] = indicator_instance.analyze()
                except Exception as e:
                    logger.error(f"Failed to analyze indicator '{name}': {e}", exc_info=True)
                    summary[name] = {"error": str(e)}
        return summary
