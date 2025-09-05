# backend/engines/strategies/ichimoku_pro.py(v21.0.0)

from __future__ import annotations
import logging
import pandas as pd
from typing import Dict, Any, Optional, List, Tuple, ClassVar

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

# IchimokuHybridPro - (v21.0.0 - Intelligent Dynamic RSI Integration)
# -------------------------------------------------------------------------
# This version marks a significant evolution by intelligently re-integrating the
# dynamic, percentile-based RSI logic, using learned patterns from benchmark
# strategies for maximum effectiveness and stability.
#
# 🚀 KEY EVOLUTIONS in v21.0.0:
# 1.  **Hybrid RSI Implementation:** The strategy now uses _is_trend_exhausted_dynamic
#     in two distinct, powerful ways:
#       - As a Keltner-style "Defensive Shield" to veto late-entry signals.
#       - As a Bollinger-style "Offensive Confirmer" to score signal timing.
# 2.  **Advanced Configurability:** A new, unified `timing_and_exhaustion_engine`
#     configuration block allows for granular control over both static and dynamic
#     modes for both the shield and the timing logic.
# 3.  **Full Backward Compatibility:** The new engine is fully configurable. By
#     setting the 'mode' to 'static', the strategy reverts to the ultra-stable
#     logic of v20.0.0, ensuring a safe fallback.
#
# This version is fully compatible with BaseStrategy v21.1.0+.

class IchimokuHybridPro(BaseStrategy):
    strategy_name: str = "IchimokuHybridPro"
    
    default_config: ClassVar[Dict[str, Any]] = {
      "operation_mode": "Regime-Aware",

      # --- NEW: Advanced, Unified, and Mode-Switchable Engine ---
      "timing_and_exhaustion_engine": {
        "enabled": True,
        # --- Timing Confirmation (Bollinger Pattern) ---
        "timing_confirm_enabled": True,
        "timing_mode": "dynamic", # "dynamic" or "static"
        "timing_apply_to_tk_cross": True,
        "timing_apply_to_breakout": False,
        "timing_static_rsi_buy_min": 50.0,
        "timing_static_rsi_sell_max": 50.0,
        "timing_dynamic_rsi_lookback": 100,
        "timing_dynamic_rsi_buy_percentile": 20,
        "timing_dynamic_rsi_sell_percentile": 80,

        # --- Exhaustion Shield (Keltner Pattern) ---
        "exhaustion_shield_enabled": True,
        "exhaustion_mode": "dynamic", # "dynamic" or "static"
        "exhaustion_static_overbought": 80.0,
        "exhaustion_static_oversold": 20.0,
        "exhaustion_dynamic_rsi_lookback": 100,
        "exhaustion_dynamic_overbought_percentile": 90,
        "exhaustion_dynamic_oversold_percentile": 10
      },

      "kumo_reversal_engine": { "enabled": True, "min_reliability": "Medium" },
      "adaptive_targeting": { "enabled": True, "atr_multiples": [1.5, 3.0, 5.0] },
      "htf_quality_scoring": {
        "enabled": True,
        "weights_htf": { "price_vs_kumo": 4, "chikou_free": 3, "future_kumo_aligned": 2, "kumo_twist": 1, "volume_spike": 1 },
        "min_score_levels": { "weak": 25.0, "normal": 40.0, "strong": 60.0 },
        "strict_mode_requires_quality": "normal"
      },
      "penalty_pct_htf_conflict": 15.0, "penalty_pct_late_entry": 10.0,
      "signal_grading_thresholds": { "strong": 80.0, "normal": 60.0 },
      "min_total_score_base": 58.0, "min_total_score_breakout_base": 60.0,
      "high_quality_score_threshold": 74.0, "min_rr_ratio": 1.6,
      "sl_hybrid_max_atr_mult": 2.0, "volume_z_relax_threshold": 1.5,
      "cooldown_bars": 3, "outlier_candle_shield": True, "outlier_atr_mult": 3.5,
      "late_entry_atr_threshold": 1.2,
      "weights_trending": { "price_vs_kumo": 2, "tk_cross_strong": 3, "tk_cross_medium": 2, "future_kumo": 1, "chikou_free": 2, "kumo_twist": 1, "volume_spike": 2, "volatility_filter": -5, "leading_timing_confirm": 2 },
      "weights_ranging": { "price_vs_kumo": 1, "tk_cross_strong": 2, "tk_cross_medium": 2, "future_kumo": 1, "chikou_free": 1, "kumo_twist": 3, "volume_spike": 2, "volatility_filter": -5, "leading_timing_confirm": 2 },
      "weights_breakout": { "price_vs_kumo": 4, "chikou_free": 3, "future_kumo": 1, "volume_spike": 3, "kumo_twist": 1 },
      "weights_reversal": { "kumo_rejection_candle": 5, "volume_spike": 3, "future_kumo_aligned": 2 },
      "market_regime_adx": 21, "sl_mode": "hybrid",
      "htf_confirmation_enabled": True, "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
      "score_weight_primary": 0.75, "score_weight_htf": 0.25,
      "htf_conflict_dampen_weight": 0.15,
      "htf_breakout_context_filter_enabled": True,
      "htf_breakout_context_levels": ["kumo", "kijun"]
    }

    # --- Helper Methods (Unchanged) ---
    def _indicator_ok(self, d: Optional[Dict]) -> bool:
        return isinstance(d, dict) and (d.get('values') or d.get('analysis'))

    def _grade_signal(self, score: float) -> str:
        thresholds = self.config.get('signal_grading_thresholds', {})
        if score >= thresholds.get('strong', 80.0): return "Strong"
        if score >= thresholds.get('normal', 60.0): return "Normal"
        return "Weak"
    
    def _generate_signal_narrative(self, direction: str, grade: str, mode: str, base_score: float, penalties: List[Dict], final_score: float, htf_details: str, htf_grade: str) -> str:
        base = f"{direction} signal ({mode} Mode, {grade} grade)"
        score_str = f"Base Score: {base_score:.2f}"
        if penalties:
            penalty_parts = [f"-{p['value_pct']:.2f}% ({p['reason']})" for p in penalties]
            penalties_str = "Penalties: " + " , ".join(penalty_parts)
        else:
            penalties_str = ""
        htf_str = f"HTF Quality: {htf_grade} ({htf_details})" if htf_details != "N/A" else ""
        final_str = f"Final: {final_score:.2f}"
        parts = [base, score_str, htf_str, penalties_str, final_str]
        return ". ".join(filter(None, parts))

    def _check_htf_breakout_context(self, direction: str) -> bool:
        # This helper remains unchanged
        if not self.htf_analysis:
            self._log_indicator_trace("HTF_Context_Check", "N/A", status="SKIPPED", reason="HTF analysis not available.")
            return True
        htf_ichi_data = self.get_indicator('ichimoku', analysis_source=self.htf_analysis)
        if not self._indicator_ok(htf_ichi_data):
            self._log_indicator_trace("HTF_Context_Check", "N/A", status="SKIPPED", reason="HTF Ichimoku data not valid.")
            return True
        htf_analysis = self._safe_get(htf_ichi_data, ['analysis'], {})
        htf_values = self._safe_get(htf_ichi_data, ['values'], {})
        htf_price = self._safe_get(self.htf_analysis, ['price_data', 'close'])
        if not self._is_valid_number(htf_price):
            self._log_indicator_trace("HTF_Context_Check", "N/A", status="SKIPPED", reason="HTF price invalid.")
            return True
        context_ok = False
        check_levels = self.config.get('htf_breakout_context_levels', []); htf_kijun = htf_values.get('kijun')
        if direction == "BUY":
            is_above_kumo = "kumo" in check_levels and htf_analysis.get('price_position') == "Above Kumo"
            is_above_kijun = "kijun" in check_levels and self._is_valid_number(htf_kijun) and htf_price > htf_kijun
            context_ok = is_above_kumo or is_above_kijun
        else:
            is_below_kumo = "kumo" in check_levels and htf_analysis.get('price_position') == "Below Kumo"
            is_below_kijun = "kijun" in check_levels and self._is_valid_number(htf_kijun) and htf_price < htf_kijun
            context_ok = is_below_kumo or is_below_kijun
        return context_ok
        
    def _score_and_normalize(self, direction: str, analysis_data: Dict, weights: Dict, trigger_type: str) -> Tuple[float, List[str], List[Dict]]:
        self._log_criteria(f"Path Check: Scoring Engine", True, f"Calculating base score for trigger '{trigger_type}'.")
        positive_score, confirmations, penalties = 0, [], []
        positive_weights = {k: v for k, v in weights.items() if v > 0}
        penalty_weights = {k: v for k, v in weights.items() if v < 0}
        max_positive_score = sum(positive_weights.values())
        ichi_data = self.get_indicator('ichimoku', analysis_source=analysis_data)
        if not self._indicator_ok(ichi_data): return 0.0, [], []
        analysis = ichi_data.get('analysis', {})
        
        def check(name: str, weight_key: str, condition: bool, reason: str = ""):
            nonlocal positive_score, confirmations
            self._log_criteria(f"ScoreComponent: {name}", condition, reason)
            if condition and weight_key in positive_weights:
                positive_score += positive_weights[weight_key]
                confirmations.append(name)
        
        # --- Standard and Universal Checks (Unchanged) ---
        is_above_kumo = analysis.get('price_position') == "Above Kumo"; is_below_kumo = analysis.get('price_position') == "Below Kumo"
        if direction == "BUY": check("Price>Kumo", 'price_vs_kumo', is_above_kumo)
        else: check("Price<Kumo", 'price_vs_kumo', is_below_kumo)
        tk_cross = str(analysis.get('tk_cross', "")).lower(); is_strong = "strong" in tk_cross
        is_aligned = ("bullish" in tk_cross and direction == "BUY") or ("bearish" in tk_cross and direction == "SELL")
        if is_aligned:
            check("Strong TK Cross", 'tk_cross_strong', is_strong, f"TK Cross: {tk_cross}")
            check("Medium TK Cross", 'tk_cross_medium', not is_strong, f"TK Cross: {tk_cross}")
        future_kumo = analysis.get('future_kumo_direction', ""); check("Future Kumo Aligned", 'future_kumo', (future_kumo == "Bullish" and direction == "BUY") or (future_kumo == "Bearish" and direction == "SELL"), f"Future Kumo: {future_kumo}")
        chikou_status = analysis.get('chikou_status', ""); check("Chikou Free", 'chikou_free', ("Free (Bullish)" in chikou_status and direction == "BUY") or ("Free (Bearish)" in chikou_status and direction == "SELL"), f"Chikou Status: {chikou_status}")
        kumo_twist = analysis.get('kumo_twist', ""); check("Kumo Twist Aligned", 'kumo_twist', (kumo_twist == "Bullish Twist" and direction == "BUY") or (kumo_twist == "Bearish Twist" and direction == "SELL"), f"Kumo Twist: {kumo_twist}")
        volume_data = self.get_indicator('volume', analysis_source=analysis_data)
        is_climactic = self._safe_get(volume_data, ['analysis', 'is_climactic_volume'], False); zscore = self._safe_get(volume_data, ['values', 'z_score'])
        is_z_spike = self._is_valid_number(zscore) and zscore >= self.config.get('volume_z_relax_threshold', 1.5)
        check("Volume Spike", 'volume_spike', is_climactic or is_z_spike, f"Climactic: {is_climactic}, Z-Score: {zscore or 'N/A':.2f}")
        if trigger_type == 'KUMO_REVERSAL': check("Kumo Rejection Candle", 'kumo_rejection_candle', True)

        # --- REFACTORED: Timing Confirmation Engine (Bollinger Pattern) ---
        engine_cfg = self.config.get('timing_and_exhaustion_engine', {})
        apply_timing = 'timing_apply_to_tk_cross' if trigger_type == 'TK_CROSS' else 'timing_apply_to_breakout'
        if engine_cfg.get('enabled', True) and engine_cfg.get('timing_confirm_enabled', True) and engine_cfg.get(apply_timing, False):
            is_timing_ok = False; rsi_reason = "RSI value not available."
            timing_mode = engine_cfg.get('timing_mode', 'static')

            if timing_mode == 'dynamic':
                # For timing, we want to confirm momentum is starting, not ending.
                # A non-exhausted state implies good timing for entry.
                is_timing_ok = not self._is_trend_exhausted_dynamic(
                    direction=direction,
                    rsi_lookback=engine_cfg.get('timing_dynamic_rsi_lookback', 100),
                    rsi_buy_percentile=engine_cfg.get('timing_dynamic_rsi_sell_percentile', 80), # Note: swapped for this logic
                    rsi_sell_percentile=engine_cfg.get('timing_dynamic_rsi_buy_percentile', 20)  # Note: swapped for this logic
                )
                # The _is_trend_exhausted_dynamic logs its own failure reason, so we don't add one here.
            else: # static mode
                rsi_data = self.get_indicator('rsi', analysis_source=analysis_data)
                rsi_value = self._safe_get(rsi_data, ['values', 'rsi'])
                if self._is_valid_number(rsi_value):
                    if direction == "BUY":
                        buy_min = engine_cfg.get('timing_static_rsi_buy_min', 50.0)
                        is_timing_ok = rsi_value >= buy_min
                        rsi_reason = f"RSI={rsi_value:.2f} vs Min={buy_min}"
                    else: # SELL
                        sell_max = engine_cfg.get('timing_static_rsi_sell_max', 50.0)
                        is_timing_ok = rsi_value <= sell_max
                        rsi_reason = f"RSI={rsi_value:.2f} vs Max={sell_max}"
                check("Timing Confirmed (Static)", "leading_timing_confirm", is_timing_ok, rsi_reason)
            
            if timing_mode == 'dynamic':
                check("Timing Confirmed (Dynamic)", "leading_timing_confirm", is_timing_ok, f"Mode: {timing_mode}")

        # --- Penalty Calculation (Unchanged) ---
        for key, raw_points in penalty_weights.items():
            condition = False; vol_state = ""
            if key == 'volatility_filter':
                vol_state = str(self._safe_get(self.get_indicator('keltner_channel', analysis_source=analysis_data), ['analysis', 'volatility_state'], '')).lower()
                condition = vol_state in ('squeeze', 'compression', 'low')
            if condition:
                pct = round((abs(raw_points) / max_positive_score) * 100, 2) if max_positive_score > 0 else abs(raw_points)
                penalties.append({'reason': f"Volatility Filter ({vol_state})", 'value_pct': pct})
        
        normalized_score = round((positive_score / max_positive_score) * 100, 2) if max_positive_score > 0 else 0.0
        return normalized_score, confirmations, penalties

    def check_signal(self) -> Optional[Dict[str, Any]]:
        # This method's structure remains largely the same, but the call to the shield is updated.
        cfg = self.config
        self._log_criteria("Path Check: Initial Validation", True, "Starting guard clauses and data validation.")
        
        if not self.price_data: self._log_final_decision("HOLD", "Missing price data."); return None
        if not isinstance(self.df, pd.DataFrame) or self.df.empty: self._log_final_decision("HOLD", "Missing final DataFrame."); return None
        
        current_bar = len(self.df) - 1
        if (current_bar - getattr(self, "last_signal_bar", -10**9)) < cfg.get('cooldown_bars', 3):
            reason = f"Cooldown Period Active ({current_bar - getattr(self, 'last_signal_bar', -999)} bars passed)."
            self._log_final_decision("HOLD", reason); return None
        
        required = ['ichimoku', 'adx', 'atr', 'volume', 'keltner_channel', 'rsi', 'patterns']
        indicators = {name: self.get_indicator(name) for name in required}
        if any(not self._indicator_ok(data) for data in indicators.values()):
            missing = [name for name, data in indicators.items() if not self._indicator_ok(data)]
            self._log_final_decision("HOLD", f"Missing or invalid required indicators: {', '.join(missing)}."); return None
        
        if cfg.get('outlier_candle_shield', True) and self._is_outlier_candle(atr_multiplier=cfg.get('outlier_atr_mult', 3.5)):
            self._log_final_decision("HOLD", "Signal blocked by Outlier Candle Shield."); return None

        self._log_criteria("Path Check: Trigger Identification", True, "Searching for TK Cross, Cloud Breakout, or Kumo Reversal triggers.")
        ichi_analysis = self._safe_get(indicators, ['ichimoku', 'analysis'], {}); ichi_values = self._safe_get(indicators, ['ichimoku', 'values'], {})
        price_pos, tk_cross = ichi_analysis.get('price_position'), str(ichi_analysis.get('tk_cross', "")).lower()
        
        best_score = -1.0
        signal_direction, trigger_type, market_regime, base_score, primary_confirms, intrinsic_penalties = None, None, None, None, [], []
        weights_map = {"TRENDING": 'weights_trending', "RANGING": 'weights_ranging', "BREAKOUT": 'weights_breakout', "REVERSAL": 'weights_reversal'}
        
        tk_cross_direction = "BUY" if "bullish" in tk_cross else "SELL" if "bearish" in tk_cross else None
        if tk_cross_direction:
            adx_val_tk = self._safe_get(indicators, ['adx', 'values', 'adx'], 0.0); tk_cross_regime = "TRENDING" if adx_val_tk > cfg.get('market_regime_adx', 21) else "RANGING"
            if price_pos == "Inside Kumo": tk_cross_regime = "RANGING"
            tk_cross_score, tk_confirms, tk_penalties = self._score_and_normalize(tk_cross_direction, self.analysis, cfg.get(weights_map[tk_cross_regime], {}), "TK_CROSS")
            if tk_cross_score > best_score:
                best_score = tk_cross_score; signal_direction = tk_cross_direction; trigger_type = "TK_CROSS"; market_regime = tk_cross_regime; base_score = tk_cross_score; primary_confirms = tk_confirms; intrinsic_penalties = tk_penalties
        
        s_a, s_b = ichi_values.get('senkou_a'), ichi_values.get('senkou_b')
        breakout_direction = "BUY" if price_pos == "Above Kumo" and self._is_valid_number(s_a, s_b) and s_a > s_b else "SELL" if price_pos == "Below Kumo" and self._is_valid_number(s_a, s_b) and s_a < s_b else None
        if breakout_direction:
            breakout_score, b_confirms, b_penalties = self._score_and_normalize(breakout_direction, self.analysis, cfg.get(weights_map["BREAKOUT"], {}), "CLOUD_BREAKOUT")
            if breakout_score > best_score:
                best_score = breakout_score; signal_direction = breakout_direction; trigger_type = "CLOUD_BREAKOUT"; market_regime = "BREAKOUT"; base_score = breakout_score; primary_confirms = b_confirms; intrinsic_penalties = b_penalties
        
        reversal_cfg = cfg.get('kumo_reversal_engine', {})
        if reversal_cfg.get('enabled', False) and price_pos == "Inside Kumo":
            for d in ["BUY", "SELL"]:
                if self._get_candlestick_confirmation(direction=d, min_reliability=reversal_cfg.get('min_reliability', 'Medium')):
                    reversal_score, r_confirms, r_penalties = self._score_and_normalize(d, self.analysis, cfg.get(weights_map["REVERSAL"], {}), "KUMO_REVERSAL")
                    if reversal_score > best_score:
                        best_score = reversal_score; signal_direction = d; trigger_type = "KUMO_REVERSAL"; market_regime = "REVERSAL"; base_score = reversal_score; primary_confirms = r_confirms; intrinsic_penalties = r_penalties

        if not signal_direction: self._log_final_decision("HOLD", "No actionable trigger found."); return None
        self._log_criteria("Primary Trigger Found", True, f"Type: {trigger_type} for {signal_direction}, Base Score: {base_score:.2f}")

        # --- REFACTORED: Exhaustion Shield (Keltner Pattern) ---
        engine_cfg = cfg.get('timing_and_exhaustion_engine', {})
        if engine_cfg.get('enabled', True) and engine_cfg.get('exhaustion_shield_enabled', True):
            exhaustion_mode = engine_cfg.get('exhaustion_mode', 'static')
            is_exhausted = False
            if exhaustion_mode == 'dynamic':
                is_exhausted = self._is_trend_exhausted_dynamic(
                    direction=signal_direction,
                    rsi_lookback=engine_cfg.get('exhaustion_dynamic_rsi_lookback', 100),
                    rsi_buy_percentile=engine_cfg.get('exhaustion_dynamic_overbought_percentile', 90),
                    rsi_sell_percentile=engine_cfg.get('exhaustion_dynamic_oversold_percentile', 10)
                )
            else: # static mode
                is_exhausted = self._is_trend_exhausted(
                    direction=signal_direction,
                    buy_exhaustion_threshold=engine_cfg.get('exhaustion_static_overbought', 80.0),
                    sell_exhaustion_threshold=engine_cfg.get('exhaustion_static_oversold', 20.0)
                )
            if is_exhausted:
                self._log_final_decision("HOLD", f"Signal blocked by Trend Exhaustion Shield (Mode: {exhaustion_mode})."); return None
            self._log_criteria("Exhaustion Shield Passed", True, f"Trend not exhausted (Mode: {exhaustion_mode}).")
        
        # --- Main Signal Processing Pipeline (Largely Unchanged) ---
        adx_val = self._safe_get(indicators, ['adx', 'values', 'adx'], 0.0)
        operation_mode = cfg.get('operation_mode', 'Regime-Aware')
        effective_mode = 'Strict' if operation_mode == 'Regime-Aware' and market_regime == 'TRENDING' else 'Adaptive' if operation_mode == 'Regime-Aware' else operation_mode
        self._log_criteria("Operation Mode Set", True, f"Market Regime: '{market_regime}' -> Effective Mode: '{effective_mode}'")
        
        htf_details, htf_quality_grade = "N/A", "N/A"; adaptive_penalties = []
        if cfg.get('htf_confirmation_enabled', True) and self.htf_analysis:
            is_htf_ok, htf_details, norm_htf_score, htf_penalties, htf_quality_grade = self._evaluate_htf(trigger_type, signal_direction)
            intrinsic_penalties.extend(htf_penalties)
            if not is_htf_ok:
                if effective_mode == 'Strict': self._log_final_decision("HOLD", f"Strict Mode blocked by HTF failure (Grade: {htf_quality_grade})."); return None
                adaptive_penalties.append({'reason': 'HTF Conflict', 'value_pct': cfg.get('penalty_pct_htf_conflict', 15.0)})
            if trigger_type == 'TK_CROSS' and base_score < cfg.get('high_quality_score_threshold', 74.0):
                 w_p, w_h = (1.0 - cfg.get('htf_conflict_dampen_weight', 0.15), cfg.get('htf_conflict_dampen_weight', 0.15)) if not is_htf_ok else (cfg.get('score_weight_primary', 0.75), cfg.get('score_weight_htf', 0.25))
                 original_base_score = base_score; base_score = (original_base_score * w_p) + (norm_htf_score * w_h)
                 self._log_criteria("Score Damping", True, f"Base score adjusted from {original_base_score:.2f} to {base_score:.2f} based on HTF alignment.")
        
        entry_price = self.price_data.get('close'); atr_val = self._safe_get(indicators, ['atr', 'values', 'atr'])
        is_late_entry = False
        if self._is_valid_number(entry_price, atr_val):
            is_late_entry = trigger_type == 'CLOUD_BREAKOUT' and abs(entry_price - ichi_values.get('senkou_a' if signal_direction == 'BUY' else 'senkou_b', entry_price)) > cfg.get('late_entry_atr_threshold', 1.2) * atr_val
        if is_late_entry:
            if effective_mode == 'Strict': self._log_final_decision("HOLD", "Strict Mode blocked by Late-Entry."); return None
            adaptive_penalties.append({'reason': 'Late Entry Risk', 'value_pct': cfg.get('penalty_pct_late_entry', 10.0)})
        
        final_score = base_score
        total_penalties = intrinsic_penalties + adaptive_penalties
        for p in total_penalties: final_score -= p.get('value_pct', 0.0)
        final_score = max(0.0, min(100.0, final_score))
        
        min_score_base = cfg.get('min_total_score_breakout_base') if trigger_type == "CLOUD_BREAKOUT" else cfg.get('min_total_score_base')
        min_score = min_score_base - 4.0 if adx_val < 18 else min_score_base - 2.0 if adx_val < cfg.get('market_regime_adx', 21) else min_score_base
        if final_score < min_score: self._log_final_decision("HOLD", f"Final score {final_score:.2f} is below minimum required {min_score:.2f}."); return None
        self._log_criteria("Final Score Passed", final_score >= min_score, f"Final Score: {final_score:.2f} vs Min: {min_score:.2f}")

        stop_loss = self._calculate_stop_loss(signal_direction, ichi_values, entry_price, atr_val, cfg)
        if not stop_loss: self._log_final_decision("HOLD", "Could not set a valid SL."); return None
        
        rr_needed = 2.0 if final_score >= cfg.get('high_quality_score_threshold', 74.0) else cfg.get('min_rr_ratio', 1.6)
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss=stop_loss)
        if not risk_params or not isinstance(risk_params.get("risk_reward_ratio"), (int, float)): self._log_final_decision("HOLD", "R/R calculation failed."); return None
        
        rr_val = risk_params.get("risk_reward_ratio")
        if rr_val < rr_needed: self._log_final_decision("HOLD", f"R/R ratio {rr_val:.2f} is below minimum requirement {rr_needed:.2f}."); return None
        self._log_criteria("Risk/Reward Passed", rr_val >= rr_needed, f"R/R: {rr_val:.2f} vs Min: {rr_needed:.2f}")

        self.last_signal_bar = current_bar
        signal_grade = self._grade_signal(final_score)
        narrative = self._generate_signal_narrative(signal_direction, signal_grade, effective_mode, base_score, total_penalties, final_score, htf_details, htf_quality_grade)
        confirmations = {"total_score": round(final_score, 2), "signal_grade": signal_grade, "narrative": narrative, "htf_details": htf_details, "htf_quality_grade": htf_quality_grade}
        
        self._log_final_decision(signal_direction, narrative)
        return {"direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations}
        
    # --- Other helpers like _evaluate_htf, _calculate_stop_loss, _calculate_smart_risk_management remain unchanged ---
    def _evaluate_htf(self, trigger_type: str, direction: str) -> Tuple[bool, str, float, List[Dict], str]:
        self._log_criteria("Path Check: HTF Evaluation", True, f"Starting HTF evaluation for trigger '{trigger_type}'.")
        htf_cfg = self.config.get('htf_quality_scoring', {})
        if not htf_cfg.get('enabled', True): return True, "Disabled", 0.0, [], "N/A"
        
        if trigger_type == 'CLOUD_BREAKOUT' and self.config.get('htf_breakout_context_filter_enabled', True):
            is_aligned = self._check_htf_breakout_context(direction)
            details = f"Context Check: {'Aligned' if is_aligned else 'Not Aligned'}"
            grade = "Normal" if is_aligned else "Fail"
            self._log_criteria("HTF Breakout Context", is_aligned, details)
            return is_aligned, details, 0.0, [], grade
        
        htf_weights = htf_cfg.get('weights_htf', {})
        norm_htf_score, htf_confirms, htf_penalties = self._score_and_normalize(direction, self.htf_analysis, htf_weights, trigger_type)
        htf_ichi = self.get_indicator('ichimoku', analysis_source=self.htf_analysis)
        htf_tk = str(self._safe_get(htf_ichi, ['analysis', 'tk_cross'], '')).lower()
        htf_dir = "BUY" if "bullish" in htf_tk else "SELL" if "bearish" in htf_tk else None
        is_direction_aligned = not (htf_dir and htf_dir != direction)
        
        levels = htf_cfg.get('min_score_levels', {})
        grade = "Fail"
        if norm_htf_score >= levels.get('strong', 60.0): grade = "Strong"
        elif norm_htf_score >= levels.get('normal', 40.0): grade = "Normal"
        elif norm_htf_score >= levels.get('weak', 25.0): grade = "Weak"
        
        required_quality = htf_cfg.get('strict_mode_requires_quality', 'normal')
        quality_map = {"Fail": 0, "Weak": 1, "Normal": 2, "Strong": 3}
        is_quality_ok = quality_map.get(grade, 0) >= quality_map.get(required_quality, 2)
        
        is_htf_ok = is_direction_aligned and is_quality_ok
        details = f"Score: {norm_htf_score:.2f}, Confirms: {','.join(htf_confirms)}, Grade: {grade}, Aligned: {is_direction_aligned}"
        self._log_criteria("HTF Scoring Results", is_htf_ok, details)
        return is_htf_ok, details, norm_htf_score, htf_penalties, grade

    def _calculate_stop_loss(self, direction: str, ichi_vals: Dict, price: float, atr: float, cfg: Dict) -> Optional[float]:
        self._log_criteria("Path Check: SL Calculation", True, f"Starting SL calculation with mode '{cfg.get('sl_mode', 'hybrid')}'.")
        if not self._is_valid_number(price, atr): self._log_criteria("SL Calculation", False, "Invalid price or ATR."); return None
        
        sl_mode = str(cfg.get('sl_mode', 'hybrid')).lower()
        calculated_sl = None
        if sl_mode == 'hybrid':
            kijun = ichi_vals.get('kijun'); kumo = ichi_vals.get('senkou_b' if direction == 'BUY' else 'senkou_a')
            structural_sl = kumo if self._is_valid_number(kumo) else kijun
            if self._is_valid_number(structural_sl):
                max_dist = cfg.get('sl_hybrid_max_atr_mult', 2.0) * atr
                if abs(price - structural_sl) > max_dist:
                    calculated_sl = price - max_dist if direction == 'BUY' else price + max_dist
                else:
                    calculated_sl = structural_sl
            else:
                calculated_sl = (price - (2.0 * atr) if direction == 'BUY' else price + (2.0 * atr))
        elif sl_mode == 'kumo': calculated_sl = ichi_vals.get('senkou_b' if direction == 'BUY' else 'senkou_a')
        elif sl_mode == 'kijun': calculated_sl = ichi_vals.get('kijun')
        
        if not self._is_valid_number(calculated_sl): self._log_criteria("SL Calculation", False, f"Could not determine a valid SL value for mode {sl_mode}."); return None
        if (direction == 'BUY' and calculated_sl >= price) or (direction == 'SELL' and calculated_sl <= price):
            self._log_criteria("SL Validation", False, f"Calculated SL {calculated_sl:.5f} is inverted against price {price:.5f}."); return None
            
        self._log_indicator_trace("Final Stop Loss", calculated_sl, reason=f"Calculated SL for {direction} signal.")
        return calculated_sl

    def _calculate_smart_risk_management(self, entry_price: float, direction: str, 
                                         stop_loss: Optional[float] = None, 
                                         sl_params: Optional[Dict[str, Any]] = None, 
                                         tp_logic: Optional[Dict[str, Any]] = None,
                                         **kwargs) -> Dict[str, Any]:
        
        final_sl, final_targets = None, []
        if sl_params and tp_logic:
            final_sl = self._calculate_sl_from_blueprint(entry_price, direction, sl_params)
            if final_sl is None: return {}
            final_targets = self._calculate_tp_from_blueprint(entry_price, final_sl, direction, tp_logic)
        elif stop_loss is not None:
            final_sl = stop_loss
            structure_data = self.get_indicator('structure'); key_levels = self._safe_get(structure_data, ['key_levels'], {})
            if direction.upper() == 'BUY': final_targets = [r['price'] for r in sorted(key_levels.get('resistances', []), key=lambda x: x['price']) if r['price'] > entry_price][:3]
            else: final_targets = [s['price'] for s in sorted(key_levels.get('supports', []), key=lambda x: x['price'], reverse=True) if s['price'] < entry_price][:3]
            self._log_indicator_trace("TP Targets", final_targets, reason="Generated from key structural levels.")
        else:
            self._log_criteria("Risk Management", False, "Cannot calculate risk without SL."); return {}

        if not final_targets:
            adaptive_cfg = self.config.get('adaptive_targeting', {})
            if adaptive_cfg.get('enabled', False):
                reward_ratios = adaptive_cfg.get('atr_multiples', [1.5, 3.0, 5.0]) 
                risk_dist = abs(entry_price - final_sl)
                final_targets = [entry_price + (risk_dist * r if direction.upper() == 'BUY' else -r * risk_dist) for r in reward_ratios]
                self._log_indicator_trace("TP Targets", final_targets, reason="Generated via Adaptive Targeting.")
            else:
                reward_ratios = self.config.get('reward_tp_ratios', [1.5, 3.0, 5.0]) 
                risk_dist = abs(entry_price - final_sl)
                final_targets = [entry_price + (risk_dist * r if direction.upper() == 'BUY' else -r * risk_dist) for r in reward_ratios]
                self._log_indicator_trace("TP Targets", final_targets, reason="Falling back to fixed R/R targets.")
        
        return self._finalize_risk_parameters(entry_price, final_sl, final_targets, direction)

