import pandas as pd
import logging
from typing import Dict, Any, Type

# ایمپورت کردن تمام اندیکاتورهای پروژه
from .indicators import *

logger = logging.getLogger(__name__)

class IndicatorAnalyzer:
    """
    The Single-Timeframe Analysis Engine for AiSignalPro (v4.0 - Final & Complete)
    ---------------------------------------------------------------------------------
    This version is designed to work as a powerful engine within a larger MTF orchestrator.
    It focuses on analyzing all indicators for a single, specific timeframe. This
    simplifies the architecture and resolves all data flow errors.
    """
    def __init__(self, df: pd.DataFrame, config: Dict[str, Any], timeframe: str):
        if not isinstance(df, pd.DataFrame) or df.empty:
            raise ValueError("Input DataFrame cannot be empty.")
        
        self.base_df = df
        self.config = config
        self.timeframe = timeframe # The single timeframe this instance is responsible for
        
        self._indicator_classes: Dict[str, Type[BaseIndicator]] = {
            'rsi': RsiIndicator, 'macd': MacdIndicator, 'bollinger': BollingerIndicator,
            'ichimoku': IchimokuIndicator, 'adx': AdxIndicator, 'supertrend': SuperTrendIndicator,
            'obv': ObvIndicator, 'stochastic': StochasticIndicator, 'cci': CciIndicator,
            'mfi': MfiIndicator, 'atr': AtrIndicator, 'patterns': PatternIndicator,
            'divergence': DivergenceIndicator, 'pivots': PivotPointIndicator,
            'structure': StructureIndicator, 'whales': WhaleIndicator,
            'ema_cross': EMACrossIndicator, 'vwap_bands': VwapBandsIndicator,
            'chandelier_exit': ChandelierExitIndicator, 'donchian_channel': DonchianChannelIndicator,
            'fast_ma': FastMAIndicator, 'williams_r': WilliamsRIndicator,
            'kelt_channel': KeltnerChannelIndicator, 'zigzag': ZigzagIndicator,
            'fibonacci': FibonacciIndicator,
        }
        self._indicator_instances: Dict[str, BaseIndicator] = {}
        self.final_df = self.base_df.copy()

    def calculate_all(self) -> 'IndicatorAnalyzer':
        """
        Calculates all enabled indicators sequentially for the single timeframe.
        This stateful, chained data flow ensures dependencies are met.
        """
        logger.info(f"Starting calculations for timeframe: {self.timeframe}")
        
        df_for_calc = self.base_df.copy()

        for name, params in self.config.items():
            if params.get('enabled', False):
                indicator_class = self._indicator_classes.get(name)
                if not indicator_class:
                    logger.warning(f"Indicator class '{name}' not found for timeframe {self.timeframe}.")
                    continue
                try:
                    instance_params = {k:v for k,v in params.items() if k != 'enabled'}
                    instance_params['timeframe'] = self.timeframe
                    
                    # ✨ REFINEMENT: The indicator is initialized with the most up-to-date dataframe
                    instance = indicator_class(df_for_calc, params=instance_params).calculate()
                    
                    # The dataframe is updated for the next indicator in the chain
                    df_for_calc = instance.df
                    self._indicator_instances[name] = instance
                    
                except Exception as e:
                    logger.error(f"Failed to calculate indicator '{name}' on timeframe '{self.timeframe}': {e}", exc_info=True)
        
        # Defragment the final DataFrame for optimal performance
        self.final_df = df_for_calc.copy()
        logger.info(f"Calculations for timeframe {self.timeframe} are complete.")
        return self

    def get_analysis_summary(self) -> Dict[str, Any]:
        """
        Analyzes all calculated indicators for the single timeframe.
        This method is efficient and bias-free.
        """
        if len(self.final_df) < 2:
            return {"status": "Insufficient Data"}
        
        summary: Dict[str, Any] = {"status": "OK"}
        
        for name, instance in self._indicator_instances.items():
            try:
                # The instance's internal dataframe is already the complete, final one.
                # Its analyze() method is internally bias-free.
                analysis = instance.analyze()
                if analysis:
                    summary[name] = analysis
            except Exception as e:
                logger.error(f"Failed to analyze indicator '{name}' on timeframe '{self.timeframe}': {e}", exc_info=True)
                summary[name] = {"error": str(e)}
                
        return summary
