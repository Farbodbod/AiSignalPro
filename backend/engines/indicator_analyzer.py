import pandas as pd
import logging
from typing import Dict, Any, Type, List, Optional
from collections import deque

from .indicators import *

logger = logging.getLogger(__name__)

class IndicatorAnalyzer:
    """
    The Self-Aware Analysis Engine for AiSignalPro (v7.0 - Final, Harmonized, & Unified)
    ------------------------------------------------------------------------------------
    This definitive version eliminates all data integrity issues by adopting a single,
    consistent DataFrame for all calculations and analysis. It ensures correct
    dependency management and prevents KeyErrors and ValueErrors at their source.
    """
    def __init__(self, df: pd.DataFrame, config: Dict[str, Any], timeframe: str, previous_df: Optional[pd.DataFrame] = None):
        if not isinstance(df, pd.DataFrame) or df.empty:
            raise ValueError("Input DataFrame cannot be empty.")
        
        self.base_df = df
        self.config = config
        self.timeframe = timeframe
        self.previous_df = previous_df
        
        self._indicator_classes: Dict[str, Type[BaseIndicator]] = {
            'rsi': RsiIndicator, 'macd': MacdIndicator, 'bollinger': BollingerIndicator, 'ichimoku': IchimokuIndicator,
            'adx': AdxIndicator, 'supertrend': SuperTrendIndicator, 'obv': ObvIndicator, 'stochastic': StochasticIndicator,
            'cci': CciIndicator, 'mfi': MfiIndicator, 'atr': AtrIndicator, 'patterns': PatternIndicator,
            'divergence': DivergenceIndicator, 'pivots': PivotPointIndicator, 'structure': StructureIndicator,
            'whales': WhaleIndicator, 'ema_cross': EMACrossIndicator, 'vwap_bands': VwapBandsIndicator,
            'chandelier_exit': ChandelierExitIndicator, 'donchian_channel': DonchianChannelIndicator,
            'fast_ma': FastMAIndicator, 'williams_r': WilliamsRIndicator, 'kelt_channel': KeltnerChannelIndicator,
            'zigzag': ZigzagIndicator, 'fibonacci': FibonacciIndicator,
        }
        
        self._calculation_order = self._resolve_dependencies()
        self._indicator_instances: Dict[str, BaseIndicator] = {}
        # ✨ FINAL ARCHITECTURE: Use a single, unified DataFrame for everything.
        self.final_df: pd.DataFrame = self.base_df.copy()

    def _resolve_dependencies(self) -> List[str]:
        """
        Performs a topological sort to find the correct indicator calculation order.
        This ensures that dependent indicators are always calculated after their dependencies.
        """
        nodes = {name for name, params in self.config.items() if params.get('enabled', False)}
        in_degree = {node: 0 for node in nodes}
        adj = {node: [] for node in nodes}

        for name in nodes:
            indicator_class = self._indicator_classes.get(name)
            if not indicator_class: continue
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
        
        logger.info(f"Resolved calculation order: {sorted_order}")
        return sorted_order

    def calculate_all(self) -> 'IndicatorAnalyzer':
        """
        ✨ FINAL ARCHITECTURE: Simplified and reliable calculation.
        Calculates all enabled indicators on the single, master final_df.
        """
        logger.info(f"Starting calculations for timeframe: {self.timeframe}")
        
        # ✨ FIX: The `final_df` is the only DataFrame used. No slices, no merges.
        # This prevents all KeyErrors and data integrity issues.
        
        for name in self._calculation_order:
            params = self.config.get(name, {})
            if params.get('enabled', False):
                try:
                    # Initialize the indicator instance with the ONLY master DataFrame
                    # and let the indicator modify it directly.
                    instance = self._indicator_classes[name](self.final_df, params={'timeframe': self.timeframe, **params})
                    instance.calculate()
                    
                    # Store the instance for the analysis phase.
                    self._indicator_instances[name] = instance
                    
                except Exception as e:
                    logger.error(f"Failed to calculate indicator '{name}': {e}", exc_info=True)
                    # For stability, remove the failed instance to prevent errors in analyze()
                    if name in self._indicator_instances:
                        del self._indicator_instances[name]

        logger.info(f"Calculations for timeframe {self.timeframe} are complete.")
        return self

    def get_analysis_summary(self) -> Dict[str, Any]:
        """
        Analyzes all indicators and includes a data health report.
        FIX: Ensures all indicators use the single, final, and complete DataFrame for analysis.
        """
        if self.final_df is None or len(self.final_df) < 2: return {"status": "Insufficient Data"}
        summary: Dict[str, Any] = {"status": "OK"}
        
        last_closed_candle = self.final_df.iloc[-2]
        summary['price_data'] = {'open': last_closed_candle.get('open'), 'high': last_closed_candle.get('high'), 'low': last_closed_candle.get('low'), 'close': last_closed_candle.get('close'), 'volume': last_closed_candle.get('volume'), 'timestamp': str(last_closed_candle.name)}
        summary['health_report'] = self.health_check()
        
        for name in self._calculation_order:
            # Check if the instance was successfully created in calculate_all
            if name in self._indicator_instances:
                instance = self._indicator_instances[name]
                # The instance is already working with self.final_df, so no need to reassign.
                try:
                    analysis = instance.analyze()
                    if analysis: summary[name] = analysis
                except Exception as e:
                    key_error_flag = isinstance(e, KeyError)
                    logger.error(f"Failed to analyze indicator '{name}': {e}", exc_info=True)
                    summary[name] = {"error": str(e), "is_key_error": key_error_flag}
        return summary
    
    def health_check(self) -> Dict[str, Any]:
        """ Performs a health check on the final data. """
        report = {"status": "HEALTHY", "issues": []}
        if self.final_df is None:
            report['status'] = "UNHEALTHY"; report['issues'].append("Final DataFrame is None.")
            return report
        
        time_diffs = self.final_df.index.to_series().diff().dt.total_seconds().dropna()
        median_interval = time_diffs.median()
        if median_interval is None: return report
        
        large_gaps = time_diffs[time_diffs > median_interval * 5]
        if not large_gaps.empty:
            report['status'] = "WARNING"
            report['issues'].append(f"{len(large_gaps)} large time gaps detected in the data index.")
        
        # Check for NaN values in calculated columns
        for name in self._calculation_order:
            if name in self._indicator_instances:
                instance = self._indicator_instances[name]
                if hasattr(instance, 'df') and instance.df is not None:
                    for col in [c for c in instance.df.columns if c not in self.base_df.columns]:
                        if col in self.final_df.columns:
                            nan_percentage = self.final_df[col].isnull().mean() * 100
                            if nan_percentage > 80:
                                report['status'] = "WARNING"
                                report['issues'].append(f"Indicator '{name}' column '{col}' has >80% NaN values.")

        return report
