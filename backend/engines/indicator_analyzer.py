import pandas as pd
import logging
from typing import Dict, Any, Type, List, Optional
from collections import deque

from .indicators import *

logger = logging.getLogger(__name__)

class IndicatorAnalyzer:
    """
    The Self-Aware Analysis Engine for AiSignalPro (v7.1 - Harmonized & Stable)
    This version includes the corrected indicator name mapping to align perfectly
    with the configuration file, eliminating naming-related KeyErrors.
    """
    def __init__(self, df: pd.DataFrame, config: Dict[str, Any], timeframe: str):
        if not isinstance(df, pd.DataFrame) or df.empty:
            raise ValueError("Input DataFrame cannot be empty.")
        
        self.base_df = df
        self.config = config
        self.timeframe = timeframe
        
        self._indicator_classes: Dict[str, Type[BaseIndicator]] = {
            'rsi': RsiIndicator, 'macd': MacdIndicator, 'bollinger': BollingerIndicator, 'ichimoku': IchimokuIndicator,
            'adx': AdxIndicator, 'supertrend': SuperTrendIndicator, 'obv': ObvIndicator, 'stochastic': StochasticIndicator,
            'cci': CciIndicator, 'mfi': MfiIndicator, 'atr': AtrIndicator, 'patterns': PatternIndicator,
            'divergence': DivergenceIndicator, 'pivots': PivotPointIndicator, 'structure': StructureIndicator,
            'whales': WhaleIndicator, 'ema_cross': EMACrossIndicator, 'vwap_bands': VwapBandsIndicator,
            'chandelier_exit': ChandelierExitIndicator, 'donchian_channel': DonchianChannelIndicator,
            'fast_ma': FastMAIndicator, 'williams_r': WilliamsRIndicator,
            # ✅ FIX: Renamed 'kelt_channel' to 'keltner_channel' to match config.json
            'keltner_channel': KeltnerChannelIndicator,
            'zigzag': ZigzagIndicator, 'fibonacci': FibonacciIndicator,
        }
        
        self._calculation_order = self._resolve_dependencies()
        
        self._indicator_instances: Dict[str, BaseIndicator] = {}
        self.final_df = None

    def _resolve_dependencies(self) -> List[str]:
        """Performs a topological sort to find the correct indicator calculation order."""
        nodes = {name for name, params in self.config.items() if params.get('enabled', False)}
        in_degree = {node: 0 for node in nodes}
        adj = {node: [] for node in nodes}

        for name in nodes:
            indicator_class = self._indicator_classes.get(name)
            if not indicator_class:
                logger.warning(f"Indicator '{name}' from config not found in _indicator_classes dict. Skipping.")
                continue
            for dep in indicator_class.dependencies:
                if dep in nodes:
                    adj[dep].append(name)
                    in_degree[name] += 1
        
        queue = deque([node for node in nodes if in_degree[node] == 0])
        sorted_order = []
        
        while queue:
            node = queue.popleft()
            sorted_order.append(node)
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(sorted_order) != len(nodes):
            cycles = {n for n in nodes if in_degree[n] > 0}
            raise ValueError(f"Circular dependency detected in indicators: {cycles}")
        
        logger.info(f"Resolved calculation order for {self.timeframe}: {sorted_order}")
        return sorted_order

    def calculate_all(self) -> 'IndicatorAnalyzer':
        """Calculates all enabled indicators in a dependency-aware order."""
        logger.info(f"Starting calculations for timeframe: {self.timeframe}")
        
        if self.timeframe and isinstance(self.base_df.index, pd.DatetimeIndex):
            rules = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}
            df_for_calc = self.base_df.resample(self.timeframe, label='right', closed='right').apply(rules).dropna()
        else:
            df_for_calc = self.base_df.copy()

        for name in self._calculation_order:
            params = self.config.get(name, {})
            if params.get('enabled', False):
                try:
                    instance_params = {k:v for k,v in params.items() if k != 'enabled'}
                    instance_params['timeframe'] = self.timeframe
                    
                    instance = self._indicator_classes[name](df_for_calc, params=instance_params).calculate()
                    
                    df_for_calc = instance.df
                    self._indicator_instances[name] = instance
                except Exception as e:
                    logger.error(f"Failed to calculate indicator '{name}' on {self.timeframe}: {e}", exc_info=True)
        
        if self.timeframe:
            self.final_df = self.base_df.copy()
            indicator_cols = [col for col in df_for_calc.columns if col not in self.base_df.columns]
            resampled_results = df_for_calc[indicator_cols]
            mapped_results = resampled_results.reindex(self.base_df.index, method='ffill')
            for col in mapped_results.columns:
                self.final_df[col] = mapped_results[col]
        else:
            self.final_df = df_for_calc.copy()

        logger.info(f"Calculations for timeframe {self.timeframe} are complete.")
        return self

    def health_check(self) -> Dict[str, Any]:
        """ Performs a health check on the final data. """
        report = {"status": "HEALTHY", "issues": []}
        if self.final_df is None:
            report['status'] = "UNHEALTHY"; report['issues'].append("Final DataFrame is None.")
            return report
        
        time_diffs = self.final_df.index.to_series().diff().dt.total_seconds().dropna()
        median_interval = time_diffs.median()
        if median_interval and median_interval > 0:
            large_gaps = time_diffs[time_diffs > median_interval * 5]
            if not large_gaps.empty:
                report['status'] = "WARNING"
                report['issues'].append(f"{len(large_gaps)} large time gaps detected.")
        
        return report

    def get_analysis_summary(self) -> Dict[str, Any]:
        """ Analyzes all indicators and includes a data health report. """
        if self.final_df is None or len(self.final_df) < 2: return {"status": "Insufficient Data"}
        summary: Dict[str, Any] = {"status": "OK"}
        
        last_closed_candle = self.final_df.iloc[-2]
        summary['price_data'] = {
            'open': last_closed_candle.get('open'), 'high': last_closed_candle.get('high'), 
            'low': last_closed_candle.get('low'), 'close': last_closed_candle.get('close'), 
            'volume': last_closed_candle.get('volume'), 'timestamp': str(last_closed_candle.name)
        }
        summary['health_report'] = self.health_check()
        
        for name in self._calculation_order:
            if name in self._indicator_instances:
                instance = self._indicator_instances[name]
                instance.df = self.final_df 
                try:
                    analysis = instance.analyze()
                    if analysis: summary[name] = analysis
                except Exception as e:
                    logger.error(f"Failed to analyze indicator '{name}' on timeframe '{self.timeframe}': {e}", exc_info=True)
                    summary[name] = {"error": str(e)}
        return summary
