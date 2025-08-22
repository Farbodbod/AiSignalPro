# engines/indicator_analyzer.py (v18.0 - The Identity Protocol)

import pandas as pd
import logging
import json
import asyncio
import inspect
from typing import Dict, Any, Type, List, Optional, Tuple
from collections import deque
from .indicators import *

logger = logging.getLogger(__name__)

def get_indicator_config_key(name: str, params: Dict[str, Any]) -> str:
    # This function remains unchanged, it is already perfect.
    try:
        filtered_params = {k: v for k, v in params.items() if k not in ["enabled", "dependencies", "name"]}
        if not filtered_params: return name
        param_str = json.dumps(filtered_params, sort_keys=True, separators=(",", ":"))
        return f"{name.lower()}_{param_str}"
    except TypeError as e:
        logger.error(f"Could not serialize params for {name}: {e}")
        param_str = "_".join(f"{k}_{v}" for k, v in sorted(params.items()) if k not in ["enabled", "dependencies", "name"])
        return f"{name.lower()}_{param_str}" if param_str else name.lower()

class IndicatorAnalyzer:
    """
    The Self-Aware Analysis Engine for AiSignalPro (v18.0 - The Identity Protocol)
    ------------------------------------------------------------------------------------------
    This definitive version introduces "Identity Injection". It now passes the
    generated `unique_key` directly into each indicator's constructor, making each
    indicator self-aware of its official ID. This perfects the DI architecture,
    creating a more robust, efficient, and architecturally pure system. A critical
    precision hotfix for iloc[-1] has also been applied.
    """
    def __init__(self, df: pd.DataFrame, indicators_config: Dict, strategies_config: Dict, timeframe: str, symbol: str, previous_df: Optional[pd.DataFrame] = None):
        if not isinstance(df, pd.DataFrame): raise ValueError("Input must be a pandas DataFrame.")
        self.base_df, self.previous_df, self.indicators_config, self.strategies_config = df, previous_df, indicators_config, strategies_config
        self.timeframe, self.symbol, self.recalc_buffer = timeframe, symbol, 250
        self._indicator_classes: Dict[str, Type[BaseIndicator]] = {cls.__name__.lower().replace('indicator', ''): cls for cls_name, cls in globals().items() if isinstance(cls, type) and issubclass(cls, BaseIndicator) and cls is not BaseIndicator}
        self._indicator_configs: Dict[str, Dict[str, Any]] = {}
        self._indicator_instances: Dict[str, BaseIndicator | Exception] = {}
        self._calculation_order: List[str] = self._resolve_dependencies()
        self.final_df: Optional[pd.DataFrame] = None

    def _resolve_dependencies(self) -> List[str]:
        # This core logic is preserved and correct.
        adj, in_degree = {}, {}
        def discover_nodes(ind_name: str, params: Dict[str, Any]):
            key = get_indicator_config_key(ind_name, params)
            if key in self._indicator_configs: return
            self._indicator_configs[key] = {'name': ind_name, 'params': params}
            adj[key], in_degree[key] = [], 0
            for dep_name, dep_params in (params.get("dependencies") or {}).items():
                discover_nodes(dep_name, dep_params)
                dep_key = get_indicator_config_key(dep_name, dep_params)
                adj[dep_key].append(key)
                in_degree[key] += 1
        for name, params_config in self.indicators_config.items():
            if params_config.get("enabled", True): discover_nodes(name, params_config.get("params", {}))
        for strat_name, strat_cfg in self.strategies_config.items():
            if strat_cfg.get("enabled", True):
                for alias, order in strat_cfg.get("indicator_configs", {}).items():
                    discover_nodes(order["name"], order.get("params", {}))
        queue = deque([k for k, deg in in_degree.items() if deg == 0]); sorted_order: List[str] = []
        while queue:
            key = queue.popleft(); sorted_order.append(key)
            for neighbor in adj.get(key, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0: queue.append(neighbor)
        if len(sorted_order) != len(self._indicator_configs):
            raise ValueError(f"Circular dependency in {self.symbol}@{self.timeframe}: {set(self._indicator_configs) - set(sorted_order)}")
        return sorted_order

    async def _calculate_and_store(self, key: str, base_df: pd.DataFrame, deps_instances: Dict[str, BaseIndicator]):
        config = self._indicator_configs[key]; name, params = config["name"], config["params"]; cls = self._indicator_classes.get(name)
        if not cls: logger.warning(f"Indicator class not found for key '{key}'"); return
        try:
            instance_params = {**params, "timeframe": self.timeframe, "symbol": self.symbol}
            
            # ✅ THE IDENTITY PROTOCOL (v18.0): Pass the unique_key directly to the constructor.
            instance = cls(df=base_df.copy(), params=instance_params, dependencies=deps_instances, unique_key=key)
            instance.calculate() # Calculate after instantiation for clarity
            self._indicator_instances[key] = instance
        except Exception as e:
            logger.error(f"Indicator calculation CRASHED for key '{key}' on {self.symbol}@{self.timeframe}: {e}", exc_info=True)
            self._indicator_instances[key] = e 

    async def calculate_all(self) -> "IndicatorAnalyzer":
        df_for_calc = self.base_df.copy()
        if self.previous_df is not None and not self.previous_df.empty:
            if df_for_calc.index.tz is None and self.previous_df.index.tz is not None: df_for_calc.index = df_for_calc.index.tz_localize(self.previous_df.index.tz)
            elif df_for_calc.index.tz is not None and self.previous_df.index.tz is None: self.previous_df.index = self.previous_df.index.tz_localize(df_for_calc.index.tz)
            df_for_calc = pd.concat([self.previous_df, df_for_calc]); df_for_calc = df_for_calc.sort_index(); df_for_calc = df_for_calc[~df_for_calc.index.duplicated(keep="last")]
        
        logger.info(f"--- Starting DI Calculations for {self.symbol}@{self.timeframe} ({len(self._calculation_order)} tasks) ---")
        tasks = [self._calculate_and_store(key, df_for_calc, {dep_key: self._indicator_instances[dep_key] for dep_key in self._get_deps_for_key(key)}) for key in self._calculation_order]
        await asyncio.gather(*tasks)
        
        self.final_df = df_for_calc
        for key, instance in self._indicator_instances.items():
            if isinstance(instance, BaseIndicator) and not instance.df.empty:
                new_cols = instance.df.columns.difference(self.final_df.columns)
                if not new_cols.empty: self.final_df = self.final_df.join(instance.df[new_cols], how='left')
        
        success_count = sum(1 for v in self._indicator_instances.values() if isinstance(v, BaseIndicator))
        logger.info(f"✅ DI Calculations complete for {self.symbol}@{self.timeframe}: {success_count} succeeded, {len(self._calculation_order) - success_count} failed/skipped.")
        if self.final_df is not None: logger.info(f"📊 Final stateful DF for {self.symbol}@{self.timeframe} now contains {len(self.final_df)} rows.")
        return self

    async def get_analysis_summary(self) -> Dict[str, Any]:
        if self.final_df is None: return {"status": "Calculation Not Run"}
        if len(self.final_df) < 2: return {"status": "Insufficient Data"}
        summary: Dict[str, Any] = {"status": "OK", "final_df": self.final_df.tail(self.recalc_buffer + 50).to_json(orient='split')}
        
        try:
            # ✅ PRECISION HOTFIX (v18.0): Use iloc[-1] to get the last *closed* candle's data.
            last_closed = self.final_df.iloc[-1]
            summary["price_data"] = {"open": last_closed["open"], "high": last_closed["high"], "low": last_closed["low"], "close": last_closed["close"], "volume": last_closed["volume"], "timestamp": str(last_closed.name)}
        except IndexError:
            return {"status": "Insufficient Data after calculations"}
        
        indicator_map = {}
        for unique_key, config in self._indicator_configs.items():
            simple_name = config['name']
            if simple_name in self.indicators_config: indicator_map[simple_name] = unique_key
        summary["_indicator_map"] = indicator_map

        total_instances = sum(1 for v in self._indicator_instances.values() if isinstance(v, BaseIndicator))
        logger.info(f"--- Starting Analysis Aggregation for {self.symbol}@{self.timeframe} ({total_instances} successful instances) ---")

        for unique_key, instance in self._indicator_instances.items():
            if not isinstance(instance, BaseIndicator): summary[unique_key] = {"status": "Calculation Failed", "values":{}, "analysis":{}}; continue
            try:
                analyze_method = getattr(instance, 'analyze', None)
                analysis = {"status": "No analyze() method found", "values":{}, "analysis":{}}
                if callable(analyze_method): analysis = analyze_method()
                summary[unique_key] = analysis
            except Exception as e:
                logger.error(f"Analysis CRASH during aggregation for '{unique_key}' on {self.symbol}@{self.timeframe}: {e}", exc_info=False)
                summary[unique_key] = {"status": f"Analysis Crashed: {e}", "values":{}, "analysis":{}}
        
        successful_analysis_count = sum(1 for v in summary.values() if isinstance(v, dict) and v.get("status") == "OK")
        logger.info(f"✅ Analysis aggregation phase for {self.symbol}@{self.timeframe} complete: {successful_analysis_count} succeeded.")
        return summary

    def _get_deps_for_key(self, key: str) -> List[str]:
        deps = []
        order = self._indicator_configs.get(key, {})
        for dep_alias, dep_params in order.get('dependencies', {}).items():
            deps.append(get_indicator_config_key(dep_alias, dep_params))
        return deps
