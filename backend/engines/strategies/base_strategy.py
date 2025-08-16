# strategies/base_strategy.py (v6.2 - Perfected Production Logging)

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union
import logging
import pandas as pd
import json

logger = logging.getLogger(__name__)

def get_indicator_config_key(name: str, params: Dict[str, Any]) -> str:
    # ... (این تابع بدون تغییر است)
    try:
        filtered_params = {k: v for k, v in params.items() if k not in ['enabled', 'dependencies', 'name']}
        if not filtered_params: return name
        param_str = json.dumps(filtered_params, sort_keys=True, separators=(',', ':'))
        return f"{name}_{param_str}"
    except TypeError:
        param_str = "_".join(f"{k}_{v}" for k, v in sorted(params.items()) if k not in ['enabled', 'dependencies', 'name'])
        return f"{name}_{param_str}" if param_str else name

class BaseStrategy(ABC):
    """
    World-Class Base Strategy Framework - (v6.2 - Perfected Production Logging)
    ---------------------------------------------------------------------------------------------
    This final version promotes the focused, step-by-step strategy logs to the INFO
    level, creating the perfect, clean production view while retaining deep-dive
    debugging capabilities at the DEBUG level.
    """
    strategy_name: str = "BaseStrategy"
    default_config: Dict[str, Any] = {}

    def __init__(self, primary_analysis: Dict[str, Any], config: Dict[str, Any], main_config: Dict[str, Any], primary_timeframe: str, symbol: str, htf_analysis: Optional[Dict[str, Any]] = None):
        # ... (این تابع بدون تغییر است)
        merged_config = {**self.default_config, **(config or {})}
        self.analysis = primary_analysis
        self.config = merged_config
        self.main_config = main_config
        self.htf_analysis = htf_analysis or {}
        self.primary_timeframe = primary_timeframe
        self.symbol = symbol
        self.price_data = self.analysis.get('price_data')
        self.df = self.analysis.get('final_df')
        self.indicator_configs = self.config.get('indicator_configs', {})
        self.log_details = {"criteria_results": []}
        self.name = config.get('name', self.strategy_name)

    def _log_criteria(self, criterion_name: str, status: bool, reason: str = ""):
        focus_symbol = self.main_config.get("general", {}).get("logging_focus_symbol")
        
        if focus_symbol and self.symbol != focus_symbol:
            return
            
        self.log_details["criteria_results"].append({"criterion": criterion_name, "status": status, "reason": reason})
        status_emoji = "✅" if status else "❌"
        # ✅ FINAL FIX: Promoted from DEBUG to INFO to appear in the clean production view.
        logger.info(f"  {status_emoji} Criterion: {self.name} on {self.primary_timeframe} - '{criterion_name}': {status}. Reason: {reason}")
    
    def _log_final_decision(self, signal: str, reason: str = ""):
        self.log_details["final_signal"] = signal
        self.log_details["final_reason"] = reason
        signal_emoji = "🟢" if signal == "BUY" else "🔴" if signal == "SELL" else "⚪️"
        logger.info(f"{signal_emoji} Final Decision: {self.name} on {self.symbol} {self.primary_timeframe} -> Signal: {signal}. Reason: {reason}")
    
    # --- (بقیه توابع کلاس بدون تغییر باقی می‌مانند) ---
    @abstractmethod
    def check_signal(self) -> Optional[Dict[str, Any]]:
        pass
    def get_indicator(self, name_or_alias: str, analysis_source: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        source = analysis_source if analysis_source is not None else self.analysis
        if not source: return None
        indicator_data = None
        if name_or_alias in self.indicator_configs:
            order = self.indicator_configs[name_or_alias]
            unique_key = get_indicator_config_key(order['name'], order.get('params', {}))
            indicator_data = source.get(unique_key)
        else:
            indicator_data = source.get(name_or_alias)
        if not indicator_data or not isinstance(indicator_data, dict):
            return None
        status = indicator_data.get("status", "").lower()
        if "error" in status or "failed" in status:
            return None
        return indicator_data
    def _get_candlestick_confirmation(self, direction: str, min_reliability: str = 'Medium') -> Optional[Dict[str, Any]]:
        pattern_analysis = self.get_indicator('patterns')
        if not pattern_analysis or 'analysis' not in pattern_analysis: return None
        reliability_map, min_reliability_score = {'Low': 0, 'Medium': 1, 'Strong': 2}, 1
        min_reliability_score = reliability_map.get(min_reliability, 1)
        target_pattern_list = 'bullish_patterns' if direction.upper() == "BUY" else 'bearish_patterns'
        found_patterns = pattern_analysis['analysis'].get(target_pattern_list, [])
        for pattern in found_patterns:
            if reliability_map.get(pattern.get('reliability'), 0) >= min_reliability_score:
                return pattern
        return None
    def _get_volume_confirmation(self) -> bool:
        whale_analysis = self.get_indicator('whales')
        if not whale_analysis: return False
        min_spike_score = self.config.get('min_whale_spike_score', 1.5)
        is_whale_activity = whale_analysis.get('analysis', {}).get('is_whale_activity', False)
        spike_score = whale_analysis.get('analysis', {}).get('spike_score', 0)
        return is_whale_activity and spike_score >= min_spike_score
    def _get_trend_confirmation(self, direction: str) -> bool:
        htf_map = self.config.get('htf_map', {})
        target_htf = htf_map.get(self.primary_timeframe)
        if not target_htf: return True
        if not self.htf_analysis or self.htf_analysis.get('price_data') is None: return False
        htf_rules, current_score = self.config.get('htf_confirmations', {}), 0
        min_required_score = htf_rules.get('min_required_score', 1)
        if "adx" in htf_rules:
            rule = htf_rules['adx']
            adx_analysis = self.get_indicator('adx', analysis_source=self.htf_analysis)
            if adx_analysis:
                adx_strength, adx_dir = adx_analysis.get('values', {}).get('adx', 0), adx_analysis.get('analysis', {}).get('direction', 'Neutral')
                if adx_strength >= rule.get('min_strength', 20) and direction.upper() in adx_dir.upper():
                    current_score += rule.get('weight', 1)
        if "supertrend" in htf_rules:
            rule = htf_rules['supertrend']
            st_analysis = self.get_indicator('supertrend', analysis_source=self.htf_analysis)
            if st_analysis:
                st_trend = st_analysis.get('analysis', {}).get('trend', 'Neutral')
                if (direction.upper() == "BUY" and "UP" in st_trend.upper()) or (direction.upper() == "SELL" and "DOWN" in st_trend.upper()):
                    current_score += rule.get('weight', 1)
        return current_score >= min_required_score
    def _calculate_smart_risk_management(self, entry_price: float, direction: str, stop_loss: float) -> Dict[str, Any]:
        if not isinstance(entry_price, (int, float)) or not isinstance(stop_loss, (int, float)):
            logger.debug(f"Smart risk calculation skipped due to invalid inputs. Entry: {entry_price}, SL: {stop_loss}")
            return {}
        if entry_price == stop_loss: return {}
        fees_pct, slippage_pct = self.main_config.get("general", {}).get("assumed_fees_pct", 0.001), self.main_config.get("general", {}).get("assumed_slippage_pct", 0.0005)
        risk_per_unit = abs(entry_price - stop_loss)
        if risk_per_unit < 1e-9: return {}
        total_risk_per_unit = risk_per_unit + (entry_price * fees_pct) + (entry_price * slippage_pct)
        structure_data = self.get_indicator('structure')
        key_levels = (structure_data.get('key_levels', {}) if structure_data else {}) or {}
        targets, resistances, supports = [], [r['price'] for r in key_levels.get('resistances', [])], [s['price'] for s in key_levels.get('supports', [])]
        if direction.upper() == 'BUY': targets = [r for r in sorted(resistances) if r > entry_price][:3]
        elif direction.upper() == 'SELL': targets = [s for s in sorted(supports, reverse=True) if s < entry_price][:3]
        if not targets:
            reward_ratios = self.config.get('reward_tp_ratios', [1.5, 3.0, 5.0])
            targets = [entry_price + (total_risk_per_unit * r if direction.upper() == 'BUY' else -total_risk_per_unit * r) for r in reward_ratios]
        if not targets: return {}
        reward_per_unit = abs(targets[0] - entry_price) - (targets[0] * fees_pct)
        actual_rr = round(reward_per_unit / total_risk_per_unit, 2) if total_risk_per_unit > 0 else 0
        return {"stop_loss": round(stop_loss, 5), "targets": [round(t, 5) for t in targets], "risk_reward_ratio": actual_rr}

