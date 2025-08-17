# engines/indicator_analyzer.py (v19.0 - Final Harmony Release)

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
    """Creates a unique, stable, and hashable key from parameters."""
    try:
        filtered_params = {
            k: v
            for k, v in params.items()
            if k not in ["enabled", "dependencies", "name"]
        }
        if not filtered_params:
            return name
        param_str = json.dumps(filtered_params, sort_keys=True, separators=(",", ":"))
        return f"{name}_{param_str}"
    except TypeError as e:
        logger.error(f"Could not serialize params for {name}: {e}")
        param_str = "_".join(
            f"{k}_{v}"
            for k, v in sorted(params.items())
            if k not in ["enabled", "dependencies", "name"]
        )
        return f"{name}_{param_str}" if param_str else name


class IndicatorAnalyzer:
    """
    The Self-Aware Analysis Engine for AiSignalPro (v19.0 - Final Harmony Release)
    ------------------------------------------------------------------------------------------
    This version reverts to a robust, sequential dependency calculation model to ensure
    stability and prevent critical failures seen in parallel processing attempts.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        config: Dict[str, Any],
        strategies_config: Dict[str, Any],
        timeframe: str,
        previous_df: Optional[pd.DataFrame] = None,
    ):
        if not isinstance(df, pd.DataFrame):
            raise ValueError("Input must be a pandas DataFrame.")
        self.base_df = df
        self.previous_df = previous_df
        self.indicators_config = config
        self.strategies_config = strategies_config
        self.timeframe = timeframe
        self.recalc_buffer = 250

        self._indicator_classes: Dict[str, Type[BaseIndicator]] = {
            "rsi": RsiIndicator,
            "macd": MacdIndicator,
            "bollinger": BollingerIndicator,
            "ichimoku": IchimokuIndicator,
            "adx": AdxIndicator,
            "supertrend": SuperTrendIndicator,
            "obv": ObvIndicator,
            "stochastic": StochasticIndicator,
            "cci": CciIndicator,
            "mfi": MfiIndicator,
            "atr": AtrIndicator,
            "patterns": PatternIndicator,
            "divergence": DivergenceIndicator,
            "pivots": PivotPointIndicator,
            "structure": StructureIndicator,
            "whales": WhaleIndicator,
            "ema_cross": EMACrossIndicator,
            "vwap_bands": VwapBandsIndicator,
            "chandelier_exit": ChandelierExitIndicator,
            "donchian_channel": DonchianChannelIndicator,
            "fast_ma": FastMAIndicator,
            "williams_r": WilliamsRIndicator,
            "keltner_channel": KeltnerChannelIndicator,
            "zigzag": ZigzagIndicator,
            "fibonacci": FibonacciIndicator,
        }

        self._indicator_configs: Dict[str, Dict[str, Any]] = {}
        self._indicator_instances: Dict[str, BaseIndicator] = {}
        self._calculation_order: List[str] = self._resolve_dependencies()
        self.final_df: Optional[pd.DataFrame] = None

    def _resolve_dependencies(self) -> List[str]:
        adj, in_degree = {}, {}

        def discover_nodes(ind_name: str, params: Dict[str, Any]):
            key = get_indicator_config_key(ind_name, params)
            if key in self._indicator_configs:
                return
            self._indicator_configs[key] = {"name": ind_name, "params": params}
            adj[key], in_degree[key] = [], 0
            for dep_name, dep_params in (params.get("dependencies") or {}).items():
                discover_nodes(dep_name, dep_params)
                dep_key = get_indicator_config_key(dep_name, dep_params)
                adj[dep_key].append(key)
                in_degree[key] += 1

        for name, params in self.indicators_config.items():
            if params.get("enabled", False):
                discover_nodes(name, params)

        for strat_name, strat_params in self.strategies_config.items():
            if strat_params.get("enabled", False):
                indicator_orders = {
                    **strat_params.get("default_params", {}).get("indicator_configs", {}),
                    **strat_params.get("indicator_configs", {}),
                }
                for alias, order in indicator_orders.items():
                    discover_nodes(order["name"], order["params"])

        queue = deque([k for k, deg in in_degree.items() if deg == 0])
        sorted_order: List[str] = []
        while queue:
            key = queue.popleft()
            sorted_order.append(key)
            for neighbor in adj.get(key, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(sorted_order) != len(self._indicator_configs):
            circular_keys = set(self._indicator_configs) - set(sorted_order)
            raise ValueError(
                f"Circular dependency in {self.timeframe}: {', '.join(circular_keys)}"
            )
        return sorted_order

    async def _calculate_indicator_task(
        self, unique_key: str, df: pd.DataFrame
    ) -> Tuple[str, str, Optional[BaseIndicator]]:
        await asyncio.sleep(0)  # Yield control for better concurrency
        config = self._indicator_configs[unique_key]
        name, params = config["name"], config["params"]
        cls = self._indicator_classes.get(name)
        if not cls:
            return "skipped", f"{unique_key}(class_not_found)", None
        
        dependencies = {}
        dep_configs = params.get("dependencies", {})
        for dep_name, dep_params in dep_configs.items():
            dep_key = get_indicator_config_key(dep_name, dep_params)
            dep_instance = self._indicator_instances.get(dep_key)
            if not isinstance(dep_instance, BaseIndicator):
                reason = f"Missing required dependency instance: '{dep_key}'"
                logger.warning(
                    f"Skipping calculation for {unique_key} on {self.timeframe}. Reason: {reason}"
                )
                return "fail", f"{unique_key}({reason})", None
            dependencies[dep_name] = dep_instance

        try:
            instance_params = {**params, "timeframe": self.timeframe}
            instance = cls(
                df=df.copy(), params=instance_params, dependencies=dependencies
            ).calculate()
            return "success", unique_key, instance
        except Exception as e:
            logger.error(
                f"Calculation task for {unique_key} on {self.timeframe} failed during execution: {e}",
                exc_info=True,
            )
            return "fail", f"{unique_key}({e})", None

    async def calculate_all(self) -> "IndicatorAnalyzer":
        if self.previous_df is not None and not self.previous_df.empty:
            df_for_calc = pd.concat([self.previous_df, self.base_df]).sort_index().pipe(
                lambda d: d[~d.index.duplicated(keep="last")]
            )
        else:
            df_for_calc = self.base_df.copy()

        logger.info(
            f"--- Starting Sequential DI Calculations for {self.timeframe} ({len(self._calculation_order)} tasks) ---"
        )
        for key in self._calculation_order:
            status, result_key, instance = await self._calculate_indicator_task(key, df_for_calc)
            if status == "success":
                self._indicator_instances[result_key] = instance
                # Update the main DataFrame with the newly calculated columns
                df_for_calc.update(instance.df, overwrite=True)
            else:
                self._indicator_instances[result_key] = None # Mark as failed
                
        self.final_df = df_for_calc
        success_count = sum(
            1 for v in self._indicator_instances.values() if isinstance(v, BaseIndicator)
        )
        failed_count = len(self._calculation_order) - success_count
        logger.info(
            f"✅ DI Calculations complete for {self.timeframe}: {success_count} succeeded, {failed_count} failed/skipped."
        )
        return self

    async def get_analysis_summary(self) -> Dict[str, Any]:
        if self.final_df is None or len(self.final_df) < 2:
            return {"status": "Insufficient Data", "analysis": {}, "key_levels": {}}

        summary: Dict[str, Any] = {"status": "OK", "final_df": self.final_df.tail(self.recalc_buffer + 50)}
        try:
            last_closed_candle = self.final_df.iloc[-2]
            summary["price_data"] = {
                "open": last_closed_candle.get("open"),
                "high": last_closed_candle.get("high"),
                "low": last_closed_candle.get("low"),
                "close": last_closed_candle.get("close"),
                "volume": last_closed_candle.get("volume"),
                "timestamp": str(last_closed_candle.name),
            }
        except IndexError:
            return {"status": "Insufficient Data after calculations", "analysis": {}, "key_levels": {}}

        successful_analysis_count = 0
        total_calculated_instances = sum(
            1 for v in self._indicator_instances.values() if isinstance(v, BaseIndicator)
        )

        for unique_key, instance in self._indicator_instances.items():
            if not isinstance(instance, BaseIndicator):
                logger.warning(f"Skipping analysis for '{unique_key}' due to failed calculation.")
                summary[unique_key] = {"status": "Dependency Calculation Failed"}
                continue
            
            try:
                analyze_method = getattr(instance, "analyze", None)
                analysis = None
                if analyze_method:
                    if inspect.iscoroutinefunction(analyze_method):
                        analysis = await analyze_method()
                    else:
                        analysis = analyze_method()
                else:
                    analysis = {"status": "No analyze() method found"}

                if analysis and analysis.get("status") == "OK":
                    successful_analysis_count += 1

                summary[unique_key] = analysis

            except Exception as e:
                logger.error(
                    f"Analysis CRASH during aggregation for '{unique_key}': {e}", exc_info=True
                )
                summary[unique_key] = {"status": f"Analysis Error: {e}"}

        failed_or_no_result_count = total_calculated_instances - successful_analysis_count
        logger.info(
            f"Analysis aggregation complete on {self.timeframe}: success={successful_analysis_count}, no_result={failed_or_no_result_count}"
        )
        return summary
