# backend/engines/strategies/ichimoku_pro.py (v10.2 - Robustness Hotfix)

from __future__ import annotations
import logging
import pandas as pd
from typing import Dict, Any, Optional, List, Tuple, ClassVar

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class IchimokuHybridPro(BaseStrategy):
    """
    IchimokuHybridPro - (v10.2 - Robustness Hotfix)
    -------------------------------------------------------------------------
    This version includes a critical hotfix to resolve a runtime ValueError
    caused by ambiguously checking the truth value of an empty DataFrame.
    The access to 'final_df' is now explicit and robust, preventing strategy
    crashes during initialization or with insufficient data.

    🚀 KEY FIXES in v10.2:
    1.  **DataFrame Truth Value Hotfix:** Replaced the unsafe `... or []`
        pattern with an explicit `isinstance(df, pd.DataFrame) and not df.empty`
        check, resolving the "truth value is ambiguous" crash.
    2.  **Minor Bugfix:** Corrected a multi-argument call to `_is_valid_number`
        to use proper chained `and` conditions.
    """
    strategy_name: str = "IchimokuHybridPro"
    
    default_config: ClassVar[Dict[str, Any]] = {
      "operation_mode": "Regime-Aware", 
      "strict_mode_requires_htf": True,
      "adaptive_htf_conflict_penalty": -10,
      "adaptive_late_entry_penalty": -5,
      "signal_grading_thresholds": { "strong": 80.0, "normal": 60.0 },
      "min_total_score_base": 58.0,
      "min_total_score_breakout_base": 60.0,
      "primary_override_threshold": 74.0,
      "min_rr_ratio": 1.6,
      "sl_hybrid_max_atr_mult": 2.0,
      "volume_z_relax_threshold": 1.5,
      "cooldown_bars": 3,
      "outlier_candle_shield": True,
      "outlier_atr_mult": 3.5,
      "late_entry_atr_threshold": 1.2,
      "weights_trending": { "price_vs_kumo": 2, "tk_cross_strong": 3, "tk_cross_medium": 2, "future_kumo": 1, "chikou_free": 2, "kumo_twist": 1, "volume_spike": 2, "volatility_filter": -5 },
      "weights_ranging": { "price_vs_kumo": 1, "tk_cross_strong": 2, "tk_cross_medium": 2, "future_kumo": 1, "chikou_free": 1, "kumo_twist": 3, "volume_spike": 2, "volatility_filter": -5 },
      "weights_breakout": { "price_vs_kumo": 4, "chikou_free": 3, "future_kumo": 1, "volume_spike": 3, "kumo_twist": 1 },
      "market_regime_adx": 21, "sl_mode": "hybrid",
      "htf_confirmation_enabled": True, "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
      "score_weight_primary": 0.75, "score_weight_htf": 0.25,
      "htf_conflict_dampen_weight": 0.15,
      "htf_breakout_context_filter_enabled": True,
      "htf_breakout_context_levels": ["kumo", "kijun"]
    }

    # --- Helper Methods [Unchanged] ---
    def _indicator_ok(self, d: Optional[Dict]) -> bool:
        return isinstance(d, dict) and (d.get('values') or d.get('analysis'))

    def _grade_signal(self, score: float) -> str:
        thresholds = self.config.get('signal_grading_thresholds', {})
        if score >= thresholds.get('strong', 80.0): return "Strong"
        if score >= thresholds.get('normal', 60.0): return "Normal"
        return "Weak"
    
    def _generate_signal_narrative(self, direction: str, grade: str, mode: str, confirms: List[str], penalties: List[Dict]) -> str:
        base = f"{direction} signal ({mode} Mode, {grade} grade)"
        confirms_str = f"Confirms: {', '.join(confirms)}" if confirms else ""
        penalties_str = f"Penalties: {', '.join([p['reason'] for p in penalties])}" if penalties else ""
        parts = [base, confirms_str, penalties_str]
        return ". ".join(filter(None, parts)) + "."

    def _check_htf_breakout_context(self, direction: str) -> bool:
        # [Unchanged]
        if not self.htf_analysis: return True
        htf_ichi_data = self.get_indicator('ichimoku', analysis_source=self.htf_analysis)
        if not self._indicator_ok(htf_ichi_data): return True
        htf_analysis = self._safe_get(htf_ichi_data, ['analysis'], {}); htf_values = self._safe_get(htf_ichi_data, ['values'], {})
        htf_price = self._safe_get(self.htf_analysis, ['price_data', 'close'])
        if not self._is_valid_number(htf_price): return True
        context_ok = False
        check_levels = self.config.get("htf_breakout_context_levels", []); htf_kijun = htf_values.get('kijun')
        if direction == "BUY":
            context_ok = ("kumo" in check_levels and htf_analysis.get('price_position') == "Above Kumo") or \
                         ("kijun" in check_levels and self._is_valid_number(htf_kijun) and htf_price > htf_kijun)
        else:
            context_ok = ("kumo" in check_levels and htf_analysis.get('price_position') == "Below Kumo") or \
                         ("kijun" in check_levels and self._is_valid_number(htf_kijun) and htf_price < htf_kijun)
        return context_ok

    def _score_ichimoku(self, direction: str, analysis_data: Dict, weights: Dict) -> Tuple[int, List[str]]:
        # [Unchanged]
        score, confirmations = 0, []
        ichi_data = self.get_indicator('ichimoku', analysis_source=analysis_data)
        if not self._indicator_ok(ichi_data): return 0, []
        analysis = ichi_data.get('analysis', {})
        def check(name: str, weight_key: str, condition: bool):
            nonlocal score, confirmations
            if condition:
                points = weights.get(weight_key, 0)
                if points != 0: score += points; confirmations.append(name)
        keltner = self.get_indicator('keltner_channel', analysis_source=analysis_data) or {}
        state = str(self._safe_get(keltner, ['analysis', 'volatility_state'], '')).lower()
        is_squeeze = state in ('squeeze', 'compression', 'low')
        check("Volatility Filter", 'volatility_filter', is_squeeze)
        is_above_kumo = analysis.get('price_position') == "Above Kumo"; is_below_kumo = analysis.get('price_position') == "Below Kumo"
        if direction == "BUY": check("Price>Kumo", 'price_vs_kumo', is_above_kumo)
        else: check("Price<Kumo", 'price_vs_kumo', is_below_kumo)
        tk_cross = str(analysis.get('tk_cross', "")).lower(); is_strong = "strong" in tk_cross
        is_aligned = ("bullish" in tk_cross and direction == "BUY") or ("bearish" in tk_cross and direction == "SELL")
        if is_aligned: check("Strong_TK_Cross", 'tk_cross_strong', is_strong); check("Medium_TK_Cross", 'tk_cross_medium', not is_strong)
        future_kumo = analysis.get('future_kumo_direction', "")
        check("Future_Kumo_Aligned", 'future_kumo', (future_kumo == "Bullish" and direction == "BUY") or (future_kumo == "Bearish" and direction == "SELL"))
        chikou_status = analysis.get('chikou_status', "")
        check("Chikou_Free", 'chikou_free', ("Free (Bullish)" in chikou_status and direction == "BUY") or ("Free (Bearish)" in chikou_status and direction == "SELL"))
        kumo_twist = analysis.get('kumo_twist', "")
        check("Kumo_Twist_Aligned", 'kumo_twist', (kumo_twist == "Bullish Twist" and direction == "BUY") or (kumo_twist == "Bearish Twist" and direction == "SELL"))
        volume_data = self.get_indicator('volume', analysis_source=analysis_data)
        is_climactic = self._safe_get(volume_data, ['analysis', 'is_climactic_volume'], False)
        zscore = self._safe_get(volume_data, ['values', 'z_score'])
        is_z_spike = self._is_valid_number(zscore) and zscore >= self.config.get('volume_z_relax_threshold', 1.5)
        check("Volume_Spike", 'volume_spike', is_climactic or is_z_spike)
        return score, confirmations

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        if not self.price_data: return None

        # --- 1. ✅ v10.2 HOTFIX: Robust DataFrame access ---
        df = self.analysis.get('final_df')
        if not isinstance(df, pd.DataFrame) or df.empty:
            self._log_final_decision("HOLD", "final_df is missing or empty.")
            return None
            
        current_bar = len(df) - 1
        if (current_bar - getattr(self, "last_signal_bar", -10**9)) < cfg.get('cooldown_bars', 3): return None

        required = ['ichimoku', 'adx', 'atr', 'volume', 'keltner_channel']
        indicators = {name: self.get_indicator(name) for name in required}
        if any(not self._indicator_ok(data) for data in indicators.values()):
            self._log_final_decision("HOLD", f"Missing indicators: {[n for n, d in indicators.items() if not self._indicator_ok(d)]}"); return None
        if cfg.get('outlier_candle_shield', True) and self._is_outlier_candle(atr_multiplier=cfg.get('outlier_atr_mult', 3.5)):
            self._log_final_decision("HOLD", "Outlier candle detected."); return None

        # --- 2. Determine Trigger & Market Regime ---
        ichi_analysis = self._safe_get(indicators, ['ichimoku', 'analysis'], {}); ichi_values = self._safe_get(indicators, ['ichimoku', 'values'], {})
        price_pos, tk_cross = ichi_analysis.get('price_position'), str(ichi_analysis.get('tk_cross', "")).lower()
        signal_direction, trigger_type = (("BUY", "TK_CROSS") if "bullish" in tk_cross else ("SELL", "TK_CROSS")) if tk_cross else (None, None)
        if not trigger_type:
            s_a, s_b = ichi_values.get('senkou_a'), ichi_values.get('senkou_b')
            # ✅ v10.2 HOTFIX: Corrected multi-argument call to _is_valid_number
            if price_pos == "Above Kumo" and self._is_valid_number(s_a) and self._is_valid_number(s_b) and s_a > s_b: signal_direction, trigger_type = "BUY", "CLOUD_BREAKOUT"
            elif price_pos == "Below Kumo" and self._is_valid_number(s_a) and self._is_valid_number(s_b) and s_a < s_b: signal_direction, trigger_type = "SELL", "CLOUD_BREAKOUT"
        if not signal_direction: self._log_final_decision("HOLD", "No primary Ichimoku trigger found."); return None
        
        adx_val = self._safe_get(indicators, ['adx', 'values', 'adx'], 0.0)
        market_regime = "BREAKOUT"
        if trigger_type == 'TK_CROSS': market_regime = "TRENDING" if adx_val > cfg.get('market_regime_adx', 21) else "RANGING"
        if price_pos == "Inside Kumo":
            if market_regime != "RANGING": self._log_criteria("Regime Override", True, f"Price inside Kumo, forcing 'RANGING' regime over '{market_regime}'.")
            market_regime = "RANGING"

        # --- 3. Determine Effective Operational Mode ---
        operation_mode = cfg.get('operation_mode', 'Regime-Aware')
        effective_mode = 'Strict' if operation_mode == 'Regime-Aware' and market_regime == 'TRENDING' else 'Adaptive' if operation_mode == 'Regime-Aware' else operation_mode
        self._log_criteria("Mode Engine", True, f"OpMode: {operation_mode}, Regime: {market_regime} -> Effective: {effective_mode}")

        # --- 4. Calculate Scores ---
        weights_map = {"TRENDING": 'weights_trending', "RANGING": 'weights_ranging', "BREAKOUT": 'weights_breakout'}
        active_weights = cfg.get(weights_map[market_regime], {})
        primary_score, primary_confirms = self._score_ichimoku(signal_direction, self.analysis, active_weights)
        max_score = sum(p for p in active_weights.values() if p > 0); norm_primary_score = round((primary_score / max_score) * 100, 2) if max_score > 0 else 0.0
        final_score = norm_primary_score
        applied_penalties = [{'reason': 'Volatility Squeeze', 'value': active_weights.get('volatility_filter')} for c in primary_confirms if c == 'Volatility Filter']
        
        # --- 5. Apply Mode-Based HTF Logic ---
        htf_ok, htf_details, norm_htf_score = True, "N/A", 0.0
        if cfg.get('htf_confirmation_enabled', True) and self.htf_analysis:
            htf_ok, htf_details, norm_htf_score = self._evaluate_htf(trigger_type, signal_direction, active_weights, max_score)
            self._log_criteria("HTF Confirmation", htf_ok, htf_details)
            if not htf_ok:
                if effective_mode == 'Strict' and cfg.get('strict_mode_requires_htf', True): self._log_final_decision("HOLD", "Strict Mode blocked by HTF failure."); return None
                elif effective_mode == 'Adaptive':
                    penalty = cfg.get('adaptive_htf_conflict_penalty', -10); final_score += penalty
                    applied_penalties.append({'reason': 'HTF Conflict', 'value': penalty})
            if htf_ok and trigger_type == 'TK_CROSS' and norm_primary_score < cfg.get('primary_override_threshold', 74.0):
                 w_p, w_h = cfg.get('score_weight_primary', 0.75), cfg.get('score_weight_htf', 0.25)
                 final_score = (norm_primary_score * w_p) + (norm_htf_score * w_h)

        # --- 6. Final Gates ---
        min_score_base = cfg.get('min_total_score_base') if trigger_type != "BREAKOUT" else cfg.get('min_total_score_breakout_base')
        min_score = min_score_base - 4.0 if adx_val < 18 else min_score_base - 2.0 if adx_val < cfg.get('market_regime_adx', 21) else min_score_base
        if final_score < min_score: self._log_final_decision("HOLD", f"Final score {final_score:.2f} < min {min_score}."); return None

        entry_price = self.price_data.get('close'); atr_val = self._safe_get(indicators, ['atr', 'values', 'atr'])
        if not self._is_valid_number(entry_price) or not self._is_valid_number(atr_val): return None
            
        is_late_entry = trigger_type == 'CLOUD_BREAKOUT' and abs(entry_price - ichi_values.get('senkou_a' if signal_direction == 'BUY' else 'senkou_b', entry_price)) > cfg.get('late_entry_atr_threshold', 1.2) * atr_val
        if is_late_entry:
            if effective_mode == 'Strict': self._log_final_decision("HOLD", "Strict Mode blocked by Late-Entry Guard."); return None
            elif effective_mode == 'Adaptive':
                penalty = cfg.get('adaptive_late_entry_penalty', -5); final_score += penalty
                applied_penalties.append({'reason': 'Late Entry Risk', 'value': penalty})
        
        stop_loss = self._calculate_stop_loss(signal_direction, ichi_values, entry_price, atr_val, cfg)
        if not stop_loss: self._log_final_decision("HOLD", "Could not set SL."); return None
        rr_needed = 2.0 if norm_primary_score >= cfg.get('primary_override_threshold', 74.0) else cfg.get('min_rr_ratio', 1.6)
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        if not isinstance(risk_params, dict) or not risk_params: self._log_final_decision("HOLD", "R/R calc failed."); return None
        rr_val = risk_params.get("risk_reward_ratio")
        if not isinstance(rr_val, (int, float)) or rr_val < rr_needed: self._log_final_decision("HOLD", f"R/R {rr_val or 'N/A'} < min {rr_needed}."); return None

        # --- 7. Signal Confirmed & Narrative Generation ---
        self.last_signal_bar = current_bar
        signal_grade = self._grade_signal(final_score)
        narrative = self._generate_signal_narrative(signal_direction, signal_grade, effective_mode, primary_confirms, applied_penalties)
        confirmations = {"total_score": round(final_score, 2), "signal_grade": signal_grade, "narrative": narrative, "trigger_type": trigger_type, "market_regime": market_regime, "primary_confirmations": primary_confirms, "htf_details": htf_details}
        self._log_final_decision(signal_direction, narrative)
        return {"direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations}

    def _evaluate_htf(self, trigger_type: str, direction: str, weights: Dict, max_score: float) -> Tuple[bool, str, float]:
        # [Unchanged]
        if trigger_type == 'CLOUD_BREAKOUT':
            htf_ok = self._check_htf_breakout_context(direction)
            details = f"Breakout Context Check: {'Pass' if htf_ok else 'Fail'}"
            return htf_ok, details, 0.0
        else: # TK_CROSS
            htf_score, htf_confirms = self._score_ichimoku(direction, self.htf_analysis, weights)
            norm_htf_score = round((htf_score / max_score) * 100, 2) if max_score > 0 else 0.0
            details = f"Score: {norm_htf_score:.2f}, Confirms: {','.join(htf_confirms)}"
            htf_ichi = self.get_indicator('ichimoku', analysis_source=self.htf_analysis)
            htf_tk = str(self._safe_get(htf_ichi, ['analysis', 'tk_cross'], '')).lower()
            htf_dir = "BUY" if "bullish" in htf_tk else "SELL" if "bearish" in htf_tk else None
            htf_ok = not (htf_dir and htf_dir != direction)
            return htf_ok, details, norm_htf_score

    def _calculate_stop_loss(self, direction: str, ichi_vals: Dict, price: float, atr: float, cfg: Dict) -> Optional[float]:
        # [Unchanged]
        sl_mode = str(cfg.get('sl_mode', 'hybrid')).lower()
        if sl_mode == 'hybrid' and atr:
            kijun = ichi_vals.get('kijun'); kumo = ichi_vals.get('senkou_b' if direction == 'BUY' else 'senkou_a')
            structural_sl = kumo if self._is_valid_number(kumo) else kijun
            if self._is_valid_number(structural_sl):
                max_dist = cfg.get('sl_hybrid_max_atr_mult', 2.0) * atr
                return (price - max_dist if direction == 'BUY' else price + max_dist) if abs(price - structural_sl) > max_dist else structural_sl
            return (price - (2.0 * atr) if direction == 'BUY' else price + (2.0 * atr))
        elif sl_mode == 'kumo': return ichi_vals.get('senkou_b' if direction == 'BUY' else 'senkou_a')
        elif sl_mode == 'kijun': return ichi_vals.get('kijun')
        return None
