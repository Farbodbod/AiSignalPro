# engines/indicator_analyzer.py (v15.3 - Log Consolidation Edition)

import pandas as pd
import logging
import json
import asyncio
from typing import Dict, Any, Type, List, Optional, Tuple
from collections import deque
import structlog # Use structlog
from .indicators import *

logger = structlog.get_logger() # Get logger via structlog

# The get_indicator_config_key function and the class __init__ and other methods remain unchanged.
# Only the logging calls inside calculate_all and get_analysis_summary are modified.

def get_indicator_config_key(name: str, params: Dict[str, Any]) -> str: # Unchanged
    try:
        filtered_params = {k: v for k, v in params.items() if k not in ['enabled', 'dependencies', 'name']};
        if not filtered_params: return name
        return f"{name}_{json.dumps(filtered_params, sort_keys=True, separators=(',', ':'))}"
    except TypeError as e:
        logger.error("Could not serialize params", name=name, error=e)
        param_str = "_".join(f"{k}_{v}" for k, v in sorted(params.items()) if k not in ['enabled', 'dependencies', 'name'])
        return f"{name}_{param_str}" if param_str else name

class IndicatorAnalyzer:
    def __init__(self, df: pd.DataFrame, config: Dict[str, Any], strategies_config: Dict[str, Any], timeframe: str, previous_df: Optional[pd.DataFrame] = None): # Unchanged
        if not isinstance(df, pd.DataFrame): raise ValueError("Input must be a pandas DataFrame.")
        self.base_df, self.previous_df, self.indicators_config, self.strategies_config, self.timeframe, self.recalc_buffer = df, previous_df, config, strategies_config, timeframe, 250
        self._indicator_classes: Dict[str, Type[BaseIndicator]] = { 'rsi': RsiIndicator, 'macd': MacdIndicator, 'bollinger': BollingerIndicator, 'ichimoku': IchimokuIndicator, 'adx': AdxIndicator, 'supertrend': SuperTrendIndicator, 'obv': ObvIndicator, 'stochastic': StochasticIndicator, 'cci': CciIndicator, 'mfi': MfiIndicator, 'atr': AtrIndicator, 'patterns': PatternIndicator, 'divergence': DivergenceIndicator, 'pivots': PivotPointIndicator, 'structure': StructureIndicator, 'whales': WhaleIndicator, 'ema_cross': EMACrossIndicator, 'vwap_bands': VwapBandsIndicator, 'chandelier_exit': ChandelierExitIndicator, 'donchian_channel': DonchianChannelIndicator, 'fast_ma': FastMAIndicator, 'williams_r': WilliamsRIndicator, 'keltner_channel': KeltnerChannelIndicator, 'zigzag': ZigzagIndicator, 'fibonacci': FibonacciIndicator, }
        self._indicator_configs: Dict[str, Dict[str, Any]] = {}; self._calculation_status: Dict[str, bool] = {}; self._indicator_instances: Dict[str, BaseIndicator] = {}; self._calculation_order: List[str] = self._resolve_dependencies(); self.final_df: Optional[pd.DataFrame] = None

    def _resolve_dependencies(self) -> List[str]: # Unchanged
        adj, in_degree = {}, {}
        def discover_nodes(ind_name: str, params: Dict[str, Any]):
            key = get_indicator_config_key(ind_name, params);
            if key in self._indicator_configs: return
            self._indicator_configs[key] = {'name': ind_name, 'params': params}; adj[key], in_degree[key] = [], 0
            for dep_name, dep_params in (params.get('dependencies') or {}).items():
                discover_nodes(dep_name, dep_params); dep_key = get_indicator_config_key(dep_name, dep_params); adj[dep_key].append(key); in_degree[key] += 1
        for name, params in self.indicators_config.items():
            if params.get('enabled', False): discover_nodes(name, params)
        for strat_name, strat_params in self.strategies_config.items():
            if strat_params.get('enabled', False):
                indicator_orders = {**strat_params.get('default_params', {}).get('indicator_configs', {}), **strat_params.get('indicator_configs', {})}
                for alias, order in indicator_orders.items(): discover_nodes(order['name'], order['params'])
        queue = deque([k for k, deg in in_degree.items() if deg == 0]); sorted_order = []
        while queue:
            key = queue.popleft(); sorted_order.append(key)
            for neighbor in adj.get(key, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0: queue.append(neighbor)
        if len(sorted_order) != len(self._indicator_configs): raise ValueError(f"Circular dependency detected in {self.timeframe}: {set(self._indicator_configs) - set(sorted_order)}")
        return sorted_order

    async def _calculate_indicator_task(self, unique_key: str, df: pd.DataFrame) -> Tuple[str, str, Optional[BaseIndicator]]: # Unchanged
        await asyncio.sleep(0); config = self._indicator_configs[unique_key]; name, params = config['name'], config['params']; cls = self._indicator_classes.get(name)
        if not cls: return 'skipped', f"{unique_key}(class_not_found)", None
        dependency_instances = {}
        for dep_alias, dep_order in (params.get('dependencies') or {}).items():
            dep_key = get_indicator_config_key(dep_alias, dep_order)
            if dep_key in self._indicator_instances: dependency_instances[dep_alias] = self._indicator_instances[dep_key]
            else: logger.warning(f"Skipping calculation for {unique_key}. Missing dependency: '{dep_key}'"); return 'fail', f"{unique_key}(Missing dependency)", None
        try:
            instance_params = {**params, 'timeframe': self.timeframe}; instance = cls(df=df.copy(), params=instance_params, dependencies=dependency_instances).calculate()
            return 'success', unique_key, instance
        except Exception as e:
            logger.debug(f"Calculation task failed.", task=unique_key, timeframe=self.timeframe, error=e, exc_info=True); return 'fail', f"{unique_key}({e})", None

    async def calculate_all(self) -> 'IndicatorAnalyzer':
        if self.previous_df is not None and not self.previous_df.empty: df_for_calc = pd.concat([self.previous_df, self.base_df]).sort_index().pipe(lambda d: d[~d.index.duplicated(keep='last')])
        else: df_for_calc = self.base_df.copy()
        
        logger.debug(f"Starting DI Calculations", timeframe=self.timeframe, tasks=len(self._calculation_order))
        for key in self._calculation_order:
            status, result_key, instance = await self._calculate_indicator_task(key, df_for_calc)
            if status == 'success': self._indicator_instances[result_key] = instance; self._calculation_status[result_key] = True; df_for_calc.update(instance.df, overwrite=True)
            else: self._calculation_status[key] = False
        
        self.final_df = df_for_calc
        success_count = sum(1 for v in self._calculation_status.values() if v)
        failed_count = len(self._calculation_order) - success_count

        # ✅ KEY UPGRADE: Consolidated multi-line log into a single log event.
        summary_message = (
            f"DI Calculations complete: {success_count} succeeded, {failed_count} failed/skipped.\n"
            f"--- Final stateful DF has {len(self.final_df)} rows. ---"
        )
        logger.info(summary_message, timeframe=self.timeframe)
        return self

    async def get_analysis_summary(self) -> Dict[str, Any]:
        if self.final_df is None or len(self.final_df) < 2: return {"status": "Insufficient Data", "analysis": {}, "key_levels": {}}
        summary: Dict[str, Any] = {"status": "OK", "final_df": self.final_df.tail(self.recalc_buffer + 50)}
        try:
            last_closed_candle = self.final_df.iloc[-2]
            summary['price_data'] = { 'open': last_closed_candle.get('open'), 'high': last_closed_candle.get('high'), 'low': last_closed_candle.get('low'), 'close': last_closed_candle.get('close'), 'volume': last_closed_candle.get('volume'), 'timestamp': str(last_closed_candle.name) }
        except IndexError:
            return {"status": "Insufficient Data after calculations", "analysis": {}, "key_levels": {}}

        total_calculated_instances = len(self._indicator_instances)
        logger.debug(f"Starting Analysis Aggregation", timeframe=self.timeframe, instances=total_calculated_instances)
        
        successful_analysis_count = 0
        for unique_key, instance in self._indicator_instances.items():
            if not self._calculation_status.get(unique_key, False): continue
            try:
                analysis = getattr(instance, "analyze", lambda: {"status": "No analyze() method found"})()
                simple_name, is_globally_enabled = self._indicator_configs[unique_key]['name'], self.indicators_config.get(simple_name, {}).get('enabled', False)
                if analysis and analysis.get("status") == "OK":
                    successful_analysis_count += 1
                    summary[unique_key], summary[simple_name] = (analysis, analysis) if is_globally_enabled else (analysis, summary.get(simple_name))
                elif is_globally_enabled:
                    summary[simple_name] = {"status": "Analysis Failed or No Data", **(analysis or {})}
            except Exception as e:
                logger.error("Analysis CRASH during aggregation", indicator=unique_key, error=e, exc_info=True); summary[unique_key] = {"status": f"Analysis Error: {e}"}
        
        # ✅ KEY UPGRADE: Consolidated multi-line log into a single log event.
        failed_or_no_result_count = total_calculated_instances - successful_analysis_count
        summary_message = (
            f"Analysis aggregation phase complete.\n"
            f"📊 Analysis Summary: {successful_analysis_count} succeeded, {failed_or_no_result_count} had no result."
        )
        logger.info(summary_message, timeframe=self.timeframe)
        return summary
