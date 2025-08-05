# engines/master_orchestrator.py (نسخه جدید و ماژولار نهایی)

import pandas as pd
import logging
from typing import Dict, Any, List, Type

from .indicator_analyzer import IndicatorAnalyzer
from .strategies import BaseStrategy, TrendRiderStrategy
# از اینجا به بعد، هر استراتژی جدیدی که بسازیم را import می‌کنیم

logger = logging.getLogger(__name__)

class MasterOrchestrator:
    """
    مغز متفکر و ارکستریتور اصلی سیستم AiSignalPro.
    این کلاس وظیفه اجرای تحلیلگر اندیکاتور و تمام استراتژی‌های فعال را بر عهده دارد.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or self._get_default_config()
        # لیست تمام جوخه‌های استراتژی که می‌خواهیم اجرا شوند
        self._strategy_classes: List[Type[BaseStrategy]] = [
            TrendRiderStrategy,
        ]
        self.ENGINE_VERSION = "15.0.0"
        logger.info(f"MasterOrchestrator v{self.ENGINE_VERSION} (Modular Architecture) initialized.")

    def _get_default_config(self) -> Dict[str, Any]:
        """تنظیمات پیش‌فرض برای استراتژی‌ها را فراهم می‌کند."""
        return {
            'TrendRiderStrategy': {
                'min_adx_strength': 25,
            },
        }

    def run_analysis_for_symbol(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        کل فرآیند تحلیل و بررسی استراتژی را برای یک نماد مشخص اجرا می‌کند.
        """
        if df.empty or len(df) < 52:
            logger.warning("DataFrame is too short for full analysis. Skipping.")
            return []

        # ۱. اجرای لایه تحلیل
        logger.info("Running Indicator Analysis Layer...")
        analyzer = IndicatorAnalyzer(df)
        analyzer.calculate_all()
        analysis_summary = analyzer.get_analysis_summary()

        # ۲. اجرای لایه تصمیم‌گیری
        logger.info("Running Strategy Decision-Making Layer...")
        valid_signals: List[Dict[str, Any]] = []
        for strategy_class in self._strategy_classes:
            try:
                strategy_name = strategy_class.__name__
                strategy_config = self.config.get(strategy_name, {})
                
                strategy_instance = strategy_class(analysis_summary, strategy_config)
                signal = strategy_instance.check_signal()
                
                if signal:
                    logger.info(f"🚀 Signal found by {strategy_name}: {signal['direction']}")
                    valid_signals.append(signal)
            except Exception as e:
                logger.error(f"Error running strategy {strategy_class.__name__}: {e}", exc_info=True)
        
        return valid_signals
