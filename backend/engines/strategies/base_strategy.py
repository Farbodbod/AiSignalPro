from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, ClassVar, Tuple
import logging
import pandas as pd
import json
from copy import deepcopy

logger = logging.getLogger(__name__)

# --- Helper functions (unchanged) ---
def get_indicator_config_key(name: str, params: Dict[str, Any]) -> str:
    try:
        filtered_params = {k: v for k, v in params.items() if k not in ['enabled', 'dependencies', 'name']}
        if not filtered_params: return name
        param_str = json.dumps(filtered_params, sort_keys=True, separators=(',', ':'))
        return f"{name}_{param_str}"
    except TypeError:
        param_str = "_".join(f"{k}_{v}" for k, v in sorted(params.items()) if k not in ['enabled', 'dependencies', 'name'])
        return f"{name}_{param_str}" if param_str else name

def deep_merge(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    result = deepcopy(dict1)
    for k, v in dict2.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict): result[k] = deep_merge(result[k], v)
        else: result[k] = v
    return result

class BaseStrategy(ABC):
    """
    World-Class Base Strategy Framework - (v25.1 - The Pivot Logic Hotfix)
    ---------------------------------------------------------------------------------------------
    This version applies a critical hotfix to the OHRE v3.0 SL Search Engine. The fix
    corrects the pivot point candidate selection logic to properly recognize broken
    resistance levels as potential support (and vice-versa), ensuring the engine
    considers all valid structural levels and preventing suboptimal SL placements.
    All other features of the Maestro Engine are preserved.
    """
    strategy_name: str = "BaseStrategy"
    default_config: ClassVar[Dict[str, Any]] = {}

    def __init__(self, primary_analysis: Dict[str, Any], config: Dict[str, Any], main_config: Dict[str, Any], primary_timeframe: str, symbol: str, htf_analysis: Optional[Dict[str, Any]] = None):
        self.analysis, self.config, self.main_config, self.htf_analysis = primary_analysis, deep_merge(self.default_config, config or {}), main_config, htf_analysis or {}
        self.primary_timeframe, self.symbol, self.price_data, self.df = primary_timeframe, symbol, self.analysis.get('price_data'), self.analysis.get('final_df')
        self.indicator_configs, self.log_details, self.name = self.config.get('indicator_configs', {}), {"criteria_results": [], "indicator_trace": [], "risk_trace": []}, self.config.get('name', self.strategy_name)

    # --- Logging Methods (Unchanged) ---
    def _log_criteria(self, criterion_name: str, status: Any, reason: str = ""):
        is_ok = bool(status); focus_symbol = self.main_config.get("general", {}).get("logging_focus_symbol");
        if focus_symbol and self.symbol != focus_symbol: return
        self.log_details["criteria_results"].append({"criterion": criterion_name, "status": is_ok, "reason": reason})
        status_emoji = "▶️" if is_ok else "‼️"; logger.info(f"  {status_emoji} Criterion: {self.name} on {self.primary_timeframe} - '{criterion_name}': {is_ok}. Reason: {reason}")
    def _log_indicator_trace(self, indicator_name: str, value: Any, status: str = "OK", reason: str = ""):
        self.log_details["indicator_trace"].append({"indicator": indicator_name, "value": str(value), "status": status, "reason": reason});
        logger.debug(f"    [Trace] Indicator: {indicator_name} -> Value: {value}, Status: {status}, Reason: {reason}")
    def _log_final_decision(self, signal: str, reason: str = ""):
        self.log_details["final_signal"], self.log_details["final_reason"] = signal, reason
        focus_symbol = self.main_config.get("general", {}).get("logging_focus_symbol"); is_focus_symbol = (self.symbol == focus_symbol)
        is_actionable_signal = (signal in ["BUY", "SELL"]); signal_emoji = "🟩" if signal == "BUY" else "🟥" if signal == "SELL" else "⬜"
        log_message = (f"{signal_emoji} Final Decision: {self.name} on {self.symbol} {self.primary_timeframe} -> Signal: {signal}. Reason: {reason}")
        if is_actionable_signal or is_focus_symbol: logger.info(log_message)
        else: logger.debug(log_message)

    @abstractmethod
    def check_signal(self) -> Optional[Dict[str, Any]]: pass

    # --- Indicator Fetching (Unchanged) ---
    def get_indicator(self, name_or_alias: str, analysis_source: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        source = analysis_source if analysis_source is not None else self.analysis;
        if not source: return None
        indicator_map = source.get('_indicator_map', {}); indicator_data, unique_key = None, None
        if name_or_alias in self.indicator_configs:
            order = self.indicator_configs[name_or_alias]; unique_key = get_indicator_config_key(order.get('name', name_or_alias), order.get('params', {}))
        elif name_or_alias in indicator_map: unique_key = indicator_map.get(name_or_alias)
        if not unique_key: self._log_indicator_trace(name_or_alias, None, status="FAILED", reason="Indicator key could not be resolved."); return None
        indicator_data = source.get(unique_key)
        if not indicator_data or not isinstance(indicator_data, dict): self._log_indicator_trace(name_or_alias, None, status="FAILED", reason=f"Missing data object for key: {unique_key}."); return None
        status = indicator_data.get("status", "").lower()
        if "error" in status or "failed" in status: self._log_indicator_trace(name_or_alias, status, status="FAILED", reason=f"Indicator reported failure status: {status}"); return None
        indicator_data.setdefault('_meta', {})['unique_key'] = unique_key; self._log_indicator_trace(name_or_alias, "OK"); return indicator_data

    # --- Universal Toolkit Helpers (Unchanged) ---
    def _safe_get(self, data: Dict, keys: List[str], default: Any = None) -> Any:
        for key in keys:
            if not isinstance(data, dict): return default
            data = data.get(key)
        return data if data is not None else default
    def _is_valid_number(self, *args) -> bool: return all(x is not None and isinstance(x, (int, float)) and pd.notna(x) for x in args)
    def _validate_blueprint(self, blueprint: Dict[str, Any]) -> bool:
        required_keys = ["direction", "entry_price", "sl_logic", "tp_logic"];
        for key in required_keys:
            if key not in blueprint: logger.error(f"Blueprint validation failed: Missing key '{key}'."); return False
        if not isinstance(blueprint.get('sl_logic'), dict) or not isinstance(blueprint.get('tp_logic'), dict):
            logger.error("Blueprint validation failed: sl_logic or tp_logic is not a dictionary."); return False
        return True
    def _get_min_score_for_tf(self, score_config: Dict[str, int]) -> int:
        tf = getattr(self, "primary_timeframe", "15m")
        if tf in ('1m','3m','5m','15m'): return int(score_config.get('low_tf', 7))
        else: return int(score_config.get('high_tf', 10))
    def _is_outlier_candle(self, atr_multiplier: float = 5.0) -> bool:
        if not self.price_data: logger.warning("Outlier check skipped: Price data not available."); return False
        atr_data = self.get_indicator('atr'); atr_value = self._safe_get(atr_data, ['values', 'atr'])
        if not self._is_valid_number(atr_value): logger.warning("Outlier check skipped: ATR not available or invalid."); return False 
        candle_range = self.price_data['high'] - self.price_data['low']
        if candle_range > (atr_value * atr_multiplier):
            self._log_criteria("Outlier Candle Shield", False, f"Outlier candle detected! Range={candle_range:.2f} > {atr_multiplier}*ATR({atr_value:.2f})"); return True
        return False
    def _get_market_regime(self, adx_threshold: float = 25.0) -> Tuple[str, float]:
        adx_data = self.get_indicator('adx'); adx_val = self._safe_get(adx_data, ['values', 'adx'])
        if not self._is_valid_number(adx_val): logger.warning("Could not determine market regime due to missing/invalid ADX."); return "UNKNOWN", 0.0
        if adx_val >= adx_threshold: return "TRENDING", adx_val
        else: return "RANGING", adx_val
    def _is_trend_exhausted(self, direction: str, buy_exhaustion_threshold: float = 80.0, sell_exhaustion_threshold: float = 20.0) -> bool:
        rsi_data = self.get_indicator('rsi'); rsi_value = self._safe_get(rsi_data, ['values', 'rsi'])
        if not self._is_valid_number(rsi_value): logger.warning("Exhaustion check skipped: RSI not available."); return False
        is_exhausted = False; reason = ""
        if direction == "BUY" and rsi_value >= buy_exhaustion_threshold: is_exhausted = True; reason = f"Trend Exhaustion! RSI ({rsi_value:.2f}) > {buy_exhaustion_threshold}."
        elif direction == "SELL" and rsi_value <= sell_exhaustion_threshold: is_exhausted = True; reason = f"Trend Exhaustion! RSI ({rsi_value:.2f}) < {sell_exhaustion_threshold}."
        if is_exhausted: self._log_criteria("Trend Exhaustion Shield", False, reason); return True
        return False
    def _is_trend_exhausted_dynamic(self, direction: str, rsi_lookback: int, rsi_buy_percentile: int, rsi_sell_percentile: int) -> bool:
        rsi_data = self.get_indicator('rsi');
        if not rsi_data or not rsi_data.get('values') or self.df is None: return False
        rsi_col = next((col for col in self.df.columns if col.startswith('RSI_')), None)
        if not rsi_col or rsi_col not in self.df.columns: return False
        rsi_series = self.df[rsi_col].dropna();
        if len(rsi_series) < rsi_lookback: return False
        window = rsi_series.tail(rsi_lookback); high_threshold = window.quantile(rsi_buy_percentile / 100.0); low_threshold = window.quantile(rsi_sell_percentile / 100.0)
        current_rsi = rsi_series.iloc[-1]
        is_exhausted = (direction == "BUY" and current_rsi >= high_threshold) or (direction == "SELL" and current_rsi <= low_threshold)
        if is_exhausted: self._log_criteria("Adaptive Exhaustion Shield", False, f"RSI {current_rsi:.2f} hit dynamic threshold (L:{low_threshold:.2f}/H:{high_threshold:.2f})");
        return is_exhausted
    def _get_candlestick_confirmation(self, direction: str, min_reliability: str = 'Medium') -> Optional[Dict[str, Any]]:
        pattern_analysis = self.get_indicator('patterns');
        if not pattern_analysis or 'analysis' not in pattern_analysis: return None
        reliability_map = {'Low': 0, 'Medium': 1, 'Strong': 2}; min_reliability_score = reliability_map.get(min_reliability, 1)
        target_pattern_list = 'bullish_patterns' if direction.upper() == "BUY" else 'bearish_patterns'
        found_patterns = (pattern_analysis.get('analysis') or {}).get(target_pattern_list, [])
        for pattern in found_patterns:
            if self._safe_get(pattern, ['reliability']) in reliability_map and reliability_map[pattern['reliability']] >= min_reliability_score: return pattern
        return None
    def _get_volume_confirmation(self) -> bool:
        volume_analysis = self._safe_get(self.get_indicator('volume'), ['analysis']);
        if not volume_analysis: return False
        return bool(volume_analysis.get('is_climactic_volume'))
    
    def _get_trend_confirmation(self, direction: str) -> bool:
        htf_map = self.config.get('htf_map', {}); target_htf = htf_map.get(self.primary_timeframe)
        if not target_htf: return True
        if not self.htf_analysis: logger.warning(f"HTF confirmation skipped: HTF analysis object is missing for '{target_htf}'."); return True
        htf_rules = self.config.get('htf_confirmations', {}); current_score = 0; min_required_score = htf_rules.get('min_required_score', 1)
        
        for rule_name, rule_params in htf_rules.items():
            if rule_name == "min_required_score": continue
            indicator_analysis = self.get_indicator(rule_name, analysis_source=self.htf_analysis)
            if not indicator_analysis: logger.warning(f"HTF confirmation failed: Required indicator '{rule_name}' missing."); continue
            
            weight = rule_params.get('weight', 1)

            if rule_name.lower() == "adx":
                adx_dir = self._safe_get(indicator_analysis, ['analysis', 'direction'], 'Neutral')
                is_aligned = (direction.upper() == "BUY" and "BULLISH" in adx_dir.upper()) or \
                             (direction.upper() == "SELL" and "BEARISH" in adx_dir.upper())
                
                adx_percentile = self._safe_get(indicator_analysis, ['analysis', 'adx_percentile'])
                min_percentile = rule_params.get('min_percentile', 75.0)
                
                if self._is_valid_number(adx_percentile) and adx_percentile >= min_percentile and is_aligned:
                    current_score += weight

            elif rule_name.lower() == "supertrend":
                st_trend = self._safe_get(indicator_analysis, ['analysis', 'trend'], 'Neutral')
                if (direction.upper() == "BUY" and "UP" in st_trend.upper()) or \
                   (direction.upper() == "SELL" and "DOWN" in st_trend.upper()):
                    current_score += weight
                    
        self._log_indicator_trace(f"HTF_Score", current_score, reason=f"Required: {min_required_score}"); 
        return current_score >= min_required_score

    # --- Final Risk Parameter Calculation (Unchanged) ---
    def _finalize_risk_parameters(self, entry_price: float, stop_loss: float, targets: List[float], direction: str) -> Dict[str, Any]:
        if not targets or not self._is_valid_number(entry_price, stop_loss) or entry_price == stop_loss: return {}
        fees_pct = self.main_config.get("general", {}).get("assumed_fees_pct", 0.0)
        slippage_pct = self.main_config.get("general", {}).get("assumed_slippage_pct", 0.0)
        reward_dist = abs(targets[0] - entry_price); risk_dist = abs(entry_price - stop_loss)
        entry_cost = entry_price * (slippage_pct + fees_pct); sl_exit_cost = stop_loss * fees_pct; tp_exit_cost = targets[0] * fees_pct
        total_risk = risk_dist + entry_cost + sl_exit_cost; total_reward = reward_dist - entry_cost - tp_exit_cost
        if total_risk < 1e-9: return {}
        actual_rr = round(total_reward / total_risk, 2) if total_risk > 0 else 0.0
        return {"stop_loss": stop_loss, "targets": targets, "risk_reward_ratio": actual_rr}

    # =========================================================================================
    # --- ✅ SURGICAL UPGRADE START: Optimized Hybrid Risk Engine (OHRE) v3.0 ---
    # This version implements the "Structural Anchor, Quantum Targets" architecture.
    # It prioritizes finding the closest, strong structural SL and then calculates
    # dynamic, momentum-aware take-profit targets.
    # =========================================================================================

    def _find_optimal_structural_sl(self, direction: str, entry_price: float) -> Optional[Dict[str, Any]]:
        """
        OHRE v3.0 - SL Search Engine.
        Finds the single best structural Stop Loss by merging, scoring, and filtering
        levels from both the 'structure' and 'pivots' indicators, then selecting the
        closest strong candidate.
        """
        engine_config = self.config.get('ohre_engine', {})
        min_strength = engine_config.get('min_level_strength', 2)
        
        candidates = []
        
        structure_data = self.get_indicator('structure')
        key_levels = self._safe_get(structure_data, ['key_levels'], {})
        s_levels = key_levels.get('supports', []) if direction == 'BUY' else key_levels.get('resistances', [])
        for level in s_levels:
            if self._is_valid_number(level.get('price')):
                candidates.append({'price': level['price'], 'strength': level.get('strength', 0), 'source': 'structure'})
                
        # ✅ HOTFIX v25.1: The pivot candidate gathering logic is now corrected.
        pivots_data = self.get_indicator('pivots')
        pivot_levels = self._safe_get(pivots_data, ['levels'], [])
        strength_map = engine_config.get('pivot_strength_map', {"S3":1,"R3":1,"S2":2,"R2":2,"S1":3,"R1":3,"P":3})
        for p_level in pivot_levels:
            # The restrictive 'S' or 'R' check is removed. All pivots are now candidates.
            # The filtering for position (above/below entry) will happen in the next step for ALL candidates.
            if self._is_valid_number(p_level.get('price')):
                candidates.append({'price': p_level['price'], 'strength': strength_map.get(p_level.get('level', ''), 1), 'source': 'pivots'})

        if not candidates: return None

        valid_candidates = []
        for cand in candidates:
            price = cand['price']
            is_valid_pos = (direction == 'BUY' and price < entry_price) or (direction == 'SELL' and price > entry_price)
            if is_valid_pos and cand['strength'] >= min_strength:
                valid_candidates.append(cand)
                
        if not valid_candidates: return None

        winner = min(valid_candidates, key=lambda x: abs(entry_price - x['price']))
        return winner

    def _calculate_dynamic_targets(self, direction: str, entry_price: float, structural_sl: float) -> List[float]:
        """
        OHRE v3.0 - TP Generation Engine.
        Calculates dynamic TPs based on the risk distance of a structural SL,
        factoring in market momentum (ADX) and volatility (ATR). Also includes
        the "Price Magnet" logic to snap targets to nearby strong structural levels.
        """
        engine_config = self.config.get('ohre_engine', {})
        fallback_config = engine_config.get('atr_fallback_engine', {})
        risk_dist = abs(entry_price - structural_sl)
        if risk_dist < 1e-9: return []

        adx_data = self.get_indicator('adx'); atr_data = self.get_indicator('atr')
        adx_percentile = self._safe_get(adx_data, ['analysis', 'adx_percentile'], 50.0)
        
        strength_multipliers = fallback_config.get('strength_multipliers', {'strong': 1.75, 'developing': 1.25, 'weak': 1.0})
        percentile_thresholds = engine_config.get('percentile_thresholds', {'strong': 80, 'developing': 40})
        
        if adx_percentile >= percentile_thresholds['strong']: strength_key = 'strong'
        elif adx_percentile >= percentile_thresholds['developing']: strength_key = 'developing'
        else: strength_key = 'weak'
        final_modifier = strength_multipliers[strength_key]

        min_rr = float(self.config.get("override_min_rr_ratio", self.main_config.get("general", {}).get("min_risk_reward_ratio", 1.5)))
        base_multiples = fallback_config.get('base_rr_multiples', [min_rr, min_rr + 1.5, min_rr + 3.0])
        final_rr_multiples = [m * final_modifier for m in base_multiples]
        
        quantum_targets = [entry_price + (risk_dist * r) for r in final_rr_multiples] if direction == "BUY" \
                         else [entry_price - (risk_dist * r) for r in final_rr_multiples]

        final_targets = []
        proximity_pct = engine_config.get('magnet_proximity_percent', 0.5) / 100.0
        min_magnet_strength = engine_config.get('min_magnet_strength', 3)
        
        structure_data = self.get_indicator('structure')
        key_levels = self._safe_get(structure_data, ['key_levels'], {})
        magnet_levels = key_levels.get('resistances', []) if direction == 'BUY' else key_levels.get('supports', [])
        
        for qt in quantum_targets:
            magnet_zone_min, magnet_zone_max = qt * (1 - proximity_pct), qt * (1 + proximity_pct)
            found_magnet = None
            for magnet in magnet_levels:
                if self._is_valid_number(magnet.get('price')) and magnet.get('strength', 0) >= min_magnet_strength and magnet_zone_min <= magnet['price'] <= magnet_zone_max:
                    found_magnet = magnet['price']
                    break
            
            final_targets.append(found_magnet if found_magnet else qt)
            
        return sorted(final_targets) if direction == 'BUY' else sorted(final_targets, reverse=True)

    def _orchestrate_static_risk(self, direction: str, entry_price: float, sl_anchor_price: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        OHRE v3.0 - The Conductor.
        Implements the definitive "Structural Anchor, Quantum Targets" architecture.
        Note: sl_anchor_price is deprecated but kept for backward compatibility.
        """
        self._log_criteria("OHRE v3.0", True, f"Initiating for {direction} signal.")
        
        best_sl_candidate = self._find_optimal_structural_sl(direction, entry_price)
        
        final_plan = None
        if best_sl_candidate:
            self._log_criteria("OHRE.SL_Engine", True, f"Found structural SL candidate at {best_sl_candidate['price']:.5f} (Source: {best_sl_candidate['source']}, Strength: {best_sl_candidate['strength']})")
            
            atr_data = self.get_indicator('atr'); atr_value = self._safe_get(atr_data, ['values', 'atr'], 0.0)
            buffer = atr_value * 0.25
            structural_sl = best_sl_candidate['price'] - buffer if direction == 'BUY' else best_sl_candidate['price'] + buffer

            final_targets = self._calculate_dynamic_targets(direction, entry_price, structural_sl)
            
            if final_targets:
                final_plan = self._finalize_risk_parameters(entry_price, structural_sl, final_targets, direction)
                if final_plan: self.log_details["risk_trace"].append({"source": "Hybrid (Structural SL + Quantum TPs)", "quality_score": 100})

        if not final_plan:
            self._log_criteria("OHRE.SL_Engine", False, "No suitable structural SL found. Executing tactical fallback.")
            final_plan = self._build_plan_from_atr_fallback(direction, entry_price)
            if final_plan: self.log_details["risk_trace"].append({"source": "Tactical Fallback (ATR-based)", "quality_score": 50})

        if final_plan:
            min_rr = float(self.config.get("override_min_rr_ratio", self.main_config.get("general", {}).get("min_risk_reward_ratio", 1.5)))
            if final_plan.get('risk_reward_ratio', 0) >= min_rr:
                 self._log_criteria("Risk Plan Finalized", True, f"Source: {self.log_details['risk_trace'][-1]['source']}, R:R: {final_plan.get('risk_reward_ratio')}")
                 return final_plan

        self._log_criteria("OHRE v3.0", False, "All risk plan providers, including fallback, failed to generate a valid plan.")
        return None

    def _build_plan_from_atr_fallback(self, direction: str, entry_price: float) -> Optional[Dict[str, Any]]:
        # This function is preserved for the fallback path
        atr_indicator = self.get_indicator('atr')
        adx_indicator = self.get_indicator('adx')
        if not atr_indicator or not adx_indicator: return None
        atr_value = self._safe_get(atr_indicator, ['values', 'atr'])
        if not self._is_valid_number(atr_value): return None
        
        engine_config = self.config.get('ohre_engine', {})
        fallback_config = engine_config.get('atr_fallback_engine', {})
        
        adx_percentile = self._safe_get(adx_indicator, ['analysis', 'adx_percentile'], 50.0)
        strength_multipliers = fallback_config.get('strength_multipliers', {'strong': 1.75, 'developing': 1.25, 'weak': 1.0})
        percentile_thresholds = engine_config.get('percentile_thresholds', {'strong': 80, 'developing': 40})
        
        if adx_percentile >= percentile_thresholds['strong']: strength_key = 'strong'
        elif adx_percentile >= percentile_thresholds['developing']: strength_key = 'developing'
        else: strength_key = 'weak'
        
        sl_atr_buffer = 1.5 * strength_multipliers[strength_key]
        stop_loss = entry_price - (atr_value * sl_atr_buffer) if direction == 'BUY' else entry_price + (atr_value * sl_atr_buffer)
        
        risk_dist = abs(entry_price - stop_loss)
        if risk_dist < 1e-9: return None

        min_rr = float(self.config.get("override_min_rr_ratio", self.main_config.get("general", {}).get("min_risk_reward_ratio", 1.5)))
        base_multiples = fallback_config.get('base_rr_multiples', [min_rr, min_rr + 1.5, min_rr + 3.0])
        final_rr_multiples = [m * strength_multipliers[strength_key] for m in base_multiples]

        final_targets = [entry_price + (risk_dist * r) for r in final_rr_multiples] if direction == "BUY" \
                   else [entry_price - (risk_dist * r) for r in final_rr_multiples]
        
        return self._finalize_risk_parameters(entry_price, stop_loss, final_targets, direction)

    # --- Original Adaptive/Dynamic Risk Engine (DEPRECATED, kept for backward compatibility) ---
    def _calculate_smart_risk_management(self, entry_price: float, direction: str, 
                                         stop_loss: Optional[float] = None, 
                                         sl_params: Optional[Dict[str, Any]] = None, 
                                         tp_logic: Optional[Dict[str, Any]] = None,
                                         **kwargs) -> Dict[str, Any]:
        logger.warning(f"Strategy '{self.name}' is calling the DEPRECATED _calculate_smart_risk_management. Please upgrade to OHRE v3.0.")
        final_sl, final_targets = None, []
        if sl_params and tp_logic:
            final_sl = self._calculate_sl_from_blueprint(entry_price, direction, sl_params)
            if not self._is_valid_number(final_sl): return {}
            final_targets = self._calculate_tp_from_blueprint(entry_price, final_sl, direction, tp_logic)
        elif self._is_valid_number(stop_loss):
            final_sl = stop_loss
            structure_data = self.get_indicator('structure'); key_levels = self._safe_get(structure_data, ['key_levels'], {})
            if direction.upper() == 'BUY': final_targets = [r['price'] for r in sorted(key_levels.get('resistances', []), key=lambda x: x['price']) if r['price'] > entry_price][:3]
            else: final_targets = [s['price'] for s in sorted(key_levels.get('supports', []), key=lambda x: x['price'], reverse=True) if s['price'] < entry_price][:3]
        else:
            return {}
        if not final_targets:
            adaptive_cfg = self.config.get('adaptive_targeting', {})
            if adaptive_cfg.get('enabled', False):
                multiples = adaptive_cfg.get('atr_multiples', [1.5, 2.5, 4.0])
                atr_data = self.get_indicator('atr')
                atr_value = self._safe_get(atr_data, ['values', 'atr'])
                if self._is_valid_number(atr_value):
                    final_targets = [entry_price + (atr_value * m if direction.upper() == 'BUY' else -atr_value * m) for m in multiples]
                    self._log_indicator_trace("TP Targets", final_targets, reason="Generated using Adaptive Targeting Engine (ATR multiples).")
                else:
                    logger.warning(f"{self.name}: Adaptive Targeting enabled but ATR is unavailable. Falling back to R/R targets.")
                    reward_ratios = self.config.get('reward_tp_ratios', [1.5, 2.5, 4.0])
                    risk_dist = abs(entry_price - final_sl)
                    final_targets = [entry_price + (risk_dist * r if direction.upper() == 'BUY' else -risk_dist * r) for r in reward_ratios]
                    self._log_indicator_trace("TP Targets", final_targets, reason="Fallback to fixed R/R targets (ATR unavailable).")
            else:
                reward_ratios = self.config.get('reward_tp_ratios', [1.5, 2.5, 4.0])
                risk_dist = abs(entry_price - final_sl)
                final_targets = [entry_price + (risk_dist * r if direction.upper() == 'BUY' else -risk_dist * r) for r in reward_ratios]
                self._log_indicator_trace("TP Targets", final_targets, reason="Generated using fallback fixed R/R targets.")
        valid_targets = [t for t in final_targets if abs(t - entry_price) > 1e-9]
        if not valid_targets:
            self._log_criteria("Risk Management", False, "No valid take-profit targets found after filtering.")
            return {}
        return self._finalize_risk_parameters(entry_price, final_sl, valid_targets, direction)
