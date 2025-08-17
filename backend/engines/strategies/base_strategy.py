# strategies/base_strategy.py (v8.1 - Critical Hotfix & Full Code)

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, ClassVar
import logging
import pandas as pd
import json
from copy import deepcopy
import structlog

logger = structlog.get_logger()

def get_indicator_config_key(name: str, params: Dict[str, Any]) -> str:
    """Creates a unique, stable, and hashable key from parameters."""
    try:
        filtered_params = {k: v for k, v in params.items() if k not in ['enabled', 'dependencies', 'name']}
        if not filtered_params: return name
        param_str = json.dumps(filtered_params, sort_keys=True, separators=(',', ':'))
        return f"{name}_{param_str}"
    except TypeError:
        param_str = "_".join(f"{k}_{v}" for k, v in sorted(params.items()) if k not in ['enabled', 'dependencies', 'name'])
        return f"{name}_{param_str}" if param_str else name

def deep_merge(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merges two dictionaries."""
    result = deepcopy(dict1)
    for k, v in dict2.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result

class BaseStrategy(ABC):
    """
    World-Class Base Strategy Framework - (v8.1 - Critical Hotfix)
    ---------------------------------------------------------------------------------------------
    This version integrates the structured logging system and contains a critical
    hotfix for an AttributeError/UnboundLocalError in the 
    _get_candlestick_confirmation helper method that could cause fatal crashes.
    """
    strategy_name: str = "BaseStrategy"
    default_config: ClassVar[Dict[str, Any]] = {}

    def __init__(self, primary_analysis: Dict[str, Any], config: Dict[str, Any], main_config: Dict[str, Any], primary_timeframe: str, symbol: str, htf_analysis: Optional[Dict[str, Any]] = None):
        self.analysis = primary_analysis
        self.config = deep_merge(self.default_config, config or {})
        self.main_config = main_config
        self.htf_analysis = htf_analysis or {}
        self.primary_timeframe = primary_timeframe
        self.symbol = symbol
        self.price_data = self.analysis.get('price_data')
        self.df = self.analysis.get('final_df')
        self.indicator_configs = self.config.get('indicator_configs', {})
        self.log_details = {"criteria_results": [], "indicator_trace": [], "risk_trace": []}
        self.name = self.config.get('name', self.strategy_name)

    def _log_criteria(self, criterion_name: str, status: bool, reason: str = ""):
        focus_symbol = self.main_config.get("general", {}).get("logging_focus_symbol")
        if focus_symbol and self.symbol != focus_symbol: return
        self.log_details["criteria_results"].append({"criterion": criterion_name, "status": status, "reason": reason})
        status_emoji = "✅" if status else "❌"
        logger.info(f"  {status_emoji} Criterion Check", 
                    strategy_name=self.name, 
                    criterion=criterion_name, 
                    status=status, 
                    reason=reason)
    
    def _log_indicator_trace(self, indicator_name: str, value: Any, status: str = "OK", reason: str = ""):
        self.log_details["indicator_trace"].append({"indicator": indicator_name, "value": str(value), "status": status, "reason": reason})
        logger.debug("Indicator trace", 
                     strategy_name=self.name, 
                     indicator=indicator_name, 
                     value=str(value), 
                     status=status, 
                     reason=reason)

    def _log_final_decision(self, signal: str, reason: str = ""):
        self.log_details["final_signal"], self.log_details["final_reason"] = signal, reason
        signal_emoji = "🟢" if signal == "BUY" else "🔴" if signal == "SELL" else "⚪️"
        logger.info(f"{signal_emoji} Final Decision", 
                    strategy_name=self.name, 
                    symbol=self.symbol, 
                    timeframe=self.primary_timeframe, 
                    signal=signal, 
                    reason=reason)

    @abstractmethod
    def check_signal(self) -> Optional[Dict[str, Any]]:
        pass

    def get_indicator(self, name_or_alias: str, analysis_source: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        source = analysis_source if analysis_source is not None else self.analysis
        if not source: return None
        indicator_data = None
        if name_or_alias in self.indicator_configs:
            order = self.indicator_configs[name_or_alias]; unique_key = get_indicator_config_key(order['name'], order.get('params', {})); indicator_data = source.get(unique_key)
        else: indicator_data = source.get(name_or_alias)
        if not indicator_data or not isinstance(indicator_data, dict):
            self._log_indicator_trace(name_or_alias, None, status="FAILED", reason="Missing or invalid data object."); return None
        status = indicator_data.get("status", "").lower()
        if "error" in status or "failed" in status:
            self._log_indicator_trace(name_or_alias, status, status="FAILED", reason=f"Indicator reported status: {status}"); return None
        self._log_indicator_trace(name_or_alias, "OK"); return indicator_data

    def _get_candlestick_confirmation(self, direction: str, min_reliability: str = 'Medium') -> Optional[Dict[str, Any]]:
        pattern_analysis = self.get_indicator('patterns')
        if not pattern_analysis or 'analysis' not in pattern_analysis: return None
        
        # ✅ CRITICAL FIX: The single-line assignment that caused the bug is split into two lines.
        reliability_map = {'Low': 0, 'Medium': 1, 'Strong': 2}
        min_reliability_score = reliability_map.get(min_reliability, 1)

        target_pattern_list = 'bullish_patterns' if direction.upper() == "BUY" else 'bearish_patterns'
        found_patterns = (pattern_analysis.get('analysis') or {}).get(target_pattern_list, [])
        for pattern in found_patterns:
            if reliability_map.get(pattern.get('reliability'), 0) >= min_reliability_score:
                return pattern
        return None

    def _get_volume_confirmation(self) -> bool:
        whale_analysis = self.get_indicator('whales');
        if not whale_analysis: return False
        min_spike_score, analysis = self.config.get('min_whale_spike_score', 1.5), whale_analysis.get('analysis') or {}
        is_whale_activity, spike_score = analysis.get('is_whale_activity', False), analysis.get('spike_score', 0)
        return is_whale_activity and spike_score >= min_spike_score

    def _get_trend_confirmation(self, direction: str) -> bool:
        htf_map, target_htf = self.config.get('htf_map', {}), htf_map.get(self.primary_timeframe)
        if not target_htf: return True
        if not self.htf_analysis or self.htf_analysis.get('price_data') is None: return False
        htf_rules, current_score, min_required_score = self.config.get('htf_confirmations', {}), 0, htf_rules.get('min_required_score', 1)
        for rule_name, rule_params in htf_rules.items():
            if rule_name == "min_required_score": continue
            indicator_analysis = self.get_indicator(rule_name, analysis_source=self.htf_analysis)
            if not indicator_analysis: continue
            weight = rule_params.get('weight', 1)
            if rule_name.lower() == "adx":
                adx_strength, adx_dir = (indicator_analysis.get('values') or {}).get('adx', 0), (indicator_analysis.get('analysis') or {}).get('direction', 'Neutral')
                if adx_strength >= rule_params.get('min_strength', 20) and direction.upper() in adx_dir.upper(): current_score += weight
            elif rule_name.lower() == "supertrend":
                st_trend = (indicator_analysis.get('analysis') or {}).get('trend', 'Neutral')
                if (direction.upper() == "BUY" and "UP" in st_trend.upper()) or (direction.upper() == "SELL" and "DOWN" in st_trend.upper()): current_score += weight
            else:
                ind_dir = (indicator_analysis.get('analysis') or {}).get('direction')
                if ind_dir and direction.upper() in ind_dir.upper(): current_score += weight
        self._log_indicator_trace(f"HTF_Score", current_score, reason=f"Required: {min_required_score}")
        return current_score >= min_required_score

    def _calculate_smart_risk_management(self, entry_price: float, direction: str, stop_loss: float) -> Dict[str, Any]:
        if not isinstance(entry_price, (int, float)) or not isinstance(stop_loss, (int, float)):
            logger.debug("Risk calc skipped due to invalid inputs", entry=entry_price, sl=stop_loss); return {}
        if entry_price == stop_loss: return {}
        fees_pct, slippage_pct = self.main_config.get("general", {}).get("assumed_fees_pct", 0.001), self.main_config.get("general", {}).get("assumed_slippage_pct", 0.0005)
        risk_per_unit = abs(entry_price - stop_loss)
        if risk_per_unit < 1e-9: return {}
        total_risk_per_unit = risk_per_unit + (entry_price * fees_pct) + (entry_price * slippage_pct)
        structure_data, key_levels = self.get_indicator('structure'), (structure_data.get('key_levels') if structure_data else {}) or {}
        targets, resistances, supports = [], (key_levels.get('resistances') or []), (key_levels.get('supports') or [])
        resistances_prices, supports_prices = [r['price'] for r in resistances], [s['price'] for s in supports]
        if direction.upper() == 'BUY': targets = [r for r in sorted(resistances_prices) if r > entry_price][:3]
        elif direction.upper() == 'SELL': targets = [s for s in sorted(supports_prices, reverse=True) if s < entry_price][:3]
        if not targets:
            logger.info("No key level targets found, using fallback.", symbol=self.symbol, timeframe=self.primary_timeframe)
            reward_ratios = self.config.get('reward_tp_ratios', [1.5, 3.0, 5.0])
            targets = [entry_price + (total_risk_per_unit * r if direction.upper() == 'BUY' else -total_risk_per_unit * r) for r in reward_ratios]
        if not targets: return {}
        reward_per_unit = abs(targets[0] - entry_price) - (targets[0] * fees_pct)
        actual_rr = round(reward_per_unit / total_risk_per_unit, 2) if total_risk_per_unit > 0 else 0
        final_params = {"stop_loss": round(stop_loss, 5), "targets": [round(t, 5) for t in targets], "risk_reward_ratio": actual_rr}
        self.log_details["risk_trace"].append(final_params)
        return final_params
