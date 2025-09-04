# backend/engines/strategies/ichimoku_pro.py (v12.3 - Narrative Engine Hotfix)

from __future__ import annotations
import logging
import pandas as pd
from typing import Dict, Any, Optional, List, Tuple, ClassVar

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class IchimokuHybridPro(BaseStrategy):
    """
    IchimokuHybridPro - (v12.3 - Narrative Engine Hotfix)
    -------------------------------------------------------------------------
    This version includes a critical hotfix for a SyntaxError in the narrative
    generation engine caused by overly complex nested f-strings. The logic has
    been refactored for clarity and robustness, resolving the final blocker
    for live deployment. All logic from v12.1/v12.2 remains intact.
    """
    strategy_name: str = "IchimokuHybridPro"
    
    default_config: ClassVar[Dict[str, Any]] = {
      "operation_mode": "Regime-Aware", 
      "htf_min_score": 20.0,
      "penalty_pct_htf_conflict": 15.0,
      "penalty_pct_late_entry": 10.0,
      
      "signal_grading_thresholds": { "strong": 80.0, "normal": 60.0 },
      "min_total_score_base": 58.0,
      "min_total_score_breakout_base": 60.0,
      "high_quality_score_threshold": 74.0,
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

    # --- Helper Methods ---
    def _indicator_ok(self, d: Optional[Dict]) -> bool:
        return isinstance(d, dict) and (d.get('values') or d.get('analysis'))

    def _grade_signal(self, score: float) -> str:
        thresholds = self.config.get('signal_grading_thresholds', {})
        if score >= thresholds.get('strong', 80.0): return "Strong"
        if score >= thresholds.get('normal', 60.0): return "Normal"
        return "Weak"
    
    def _generate_signal_narrative(self, direction: str, grade: str, mode: str, base_score: float, penalties: List[Dict], final_score: float) -> str:
        base = f"{direction} signal ({mode} Mode, {grade} grade)"
        score_str = f"Base Score: {base_score:.2f}"
        
        # ✅ v12.3 SYNTAX HOTFIX: Refactored for robustness
        if penalties:
            penalty_parts = [f"-{p['value_pct']:.2f}% ({p['reason']})" for p in penalties]
            penalties_str = "Penalties: " + " , ".join(penalty_parts)
        else:
            penalties_str = ""
            
        final_str = f"Final: {final_score:.2f}"
        parts = [base, score_str, penalties_str, final_str]
        return ". ".join(filter(None, parts))

    def _score_and_normalize(self, direction: str, analysis_data: Dict, weights: Dict) -> Tuple[float, List[str], List[Dict]]:
        positive_score, confirmations, penalties = 0, [], []
        
        positive_weights = {k: v for k, v in weights.items() if v > 0}
        penalty_weights = {k: v for k, v in weights.items() if v < 0}
        max_positive_score = sum(positive_weights.values())

        ichi_data = self.get_indicator('ichimoku', analysis_source=analysis_data)
        if not self._indicator_ok(ichi_data): return 0.0, [], []
        
        analysis = ichi_data.get('analysis', {})
        def check(name: str, weight_key: str, condition: bool):
            nonlocal positive_score, confirmations
            if condition and weight_key in positive_weights:
                positive_score += positive_weights[weight_key]
                confirmations.append(name)
        
        # Positive Scoring
        is_above_kumo = analysis.get('price_position') == "Above Kumo"; is_below_kumo = analysis.get('price_position') == "Below Kumo"
        if direction == "BUY": check("Price>Kumo", 'price_vs_kumo', is_above_kumo)
        else: check("Price<Kumo", 'price_vs_kumo', is_below_kumo)
        tk_cross = str(analysis.get('tk_cross', "")).lower(); is_strong = "strong" in tk_cross
        is_aligned = ("bullish" in tk_cross and direction == "BUY") or ("bearish" in tk_cross and direction == "SELL")
        if is_aligned: check("Strong_TK_Cross", 'tk_cross_strong', is_strong); check("Medium_TK_Cross", 'tk_cross_medium', not is_strong)
        future_kumo = analysis.get('future_kumo_direction', ""); check("Future_Kumo_Aligned", 'future_kumo', (future_kumo == "Bullish" and direction == "BUY") or (future_kumo == "Bearish" and direction == "SELL"))
        chikou_status = analysis.get('chikou_status', ""); check("Chikou_Free", 'chikou_free', ("Free (Bullish)" in chikou_status and direction == "BUY") or ("Free (Bearish)" in chikou_status and direction == "SELL"))
        kumo_twist = analysis.get('kumo_twist', ""); check("Kumo_Twist_Aligned", 'kumo_twist', (kumo_twist == "Bullish Twist" and direction == "BUY") or (kumo_twist == "Bearish Twist" and direction == "SELL"))
        volume_data = self.get_indicator('volume', analysis_source=analysis_data)
        is_climactic = self._safe_get(volume_data, ['analysis', 'is_climactic_volume'], False); zscore = self._safe_get(volume_data, ['values', 'z_score'])
        is_z_spike = self._is_valid_number(zscore) and zscore >= self.config.get('volume_z_relax_threshold', 1.5); check("Volume_Spike", 'volume_spike', is_climactic or is_z_spike)
        
        # Unified Penalty Calculation
        for key, raw_points in penalty_weights.items():
            condition = False
            if key == 'volatility_filter':
                condition = str(self._safe_get(self.get_indicator('keltner_channel', analysis_source=analysis_data), ['analysis', 'volatility_state'], '')).lower() in ('squeeze', 'compression', 'low')
            
            if condition:
                pct = round((abs(raw_points) / max_positive_score) * 100, 2) if max_positive_score > 0 else abs(raw_points)
                penalties.append({'reason': key.replace('_', ' ').title(), 'value_pct': pct})
        
        normalized_score = round((positive_score / max_positive_score) * 100, 2) if max_positive_score > 0 else 0.0
        return normalized_score, confirmations, penalties

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        if not self.price_data: return None
        df = self.analysis.get('final_df');
        if not isinstance(df, pd.DataFrame) or df.empty: return None
        current_bar = len(df) - 1
        if (current_bar - getattr(self, "last_signal_bar", -10**9)) < cfg.get('cooldown_bars', 3): return None
        
        required = ['ichimoku', 'adx', 'atr', 'volume', 'keltner_channel']
        indicators = {name: self.get_indicator(name) for name in required}
        if any(not self._indicator_ok(data) for data in indicators.values()): self._log_final_decision("HOLD", f"Missing indicators."); return None
        if cfg.get('outlier_candle_shield', True) and self._is_outlier_candle(atr_multiplier=cfg.get('outlier_atr_mult', 3.5)): self._log_final_decision("HOLD", "Outlier candle."); return None

        ichi_analysis = self._safe_get(indicators, ['ichimoku', 'analysis'], {}); ichi_values = self._safe_get(indicators, ['ichimoku', 'values'], {})
        price_pos, tk_cross = ichi_analysis.get('price_position'), str(ichi_analysis.get('tk_cross', "")).lower()
        signal_direction, trigger_type = (("BUY", "TK_CROSS") if "bullish" in tk_cross else ("SELL", "TK_CROSS")) if tk_cross else (None, None)
        if not trigger_type:
            s_a, s_b = ichi_values.get('senkou_a'), ichi_values.get('senkou_b')
            if price_pos == "Above Kumo" and self._is_valid_number(s_a) and self._is_valid_number(s_b) and s_a > s_b: signal_direction, trigger_type = "BUY", "CLOUD_BREAKOUT"
            elif price_pos == "Below Kumo" and self._is_valid_number(s_a) and self._is_valid_number(s_b) and s_a < s_b: signal_direction, trigger_type = "SELL", "CLOUD_BREAKOUT"
        if not signal_direction: self._log_final_decision("HOLD", "No trigger found."); return None
        
        adx_val = self._safe_get(indicators, ['adx', 'values', 'adx'], 0.0)
        market_regime = "BREAKOUT";
        if trigger_type == 'TK_CROSS': market_regime = "TRENDING" if adx_val > cfg.get('market_regime_adx', 21) else "RANGING"
        if price_pos == "Inside Kumo": market_regime = "RANGING"

        operation_mode = cfg.get('operation_mode', 'Regime-Aware')
        effective_mode = 'Strict' if operation_mode == 'Regime-Aware' and market_regime == 'TRENDING' else 'Adaptive' if operation_mode == 'Regime-Aware' else operation_mode
        
        weights_map = {"TRENDING": 'weights_trending', "RANGING": 'weights_ranging', "BREAKOUT": 'weights_breakout'}
        active_weights = cfg.get(weights_map[market_regime], {})
        norm_primary_score, primary_confirms, intrinsic_penalties = self._score_and_normalize(signal_direction, self.analysis, active_weights)
        base_score = norm_primary_score; htf_details = "N/A"
        
        adaptive_penalties = []
        htf_ok = True
        if cfg.get('htf_confirmation_enabled', True) and self.htf_analysis:
            htf_ok, htf_details, norm_htf_score, htf_penalties = self._evaluate_htf(trigger_type, signal_direction, active_weights)
            intrinsic_penalties.extend(htf_penalties)
            if not htf_ok and effective_mode == 'Strict': self._log_final_decision("HOLD", f"Strict Mode blocked by HTF failure ({htf_details})."); return None
            if trigger_type == 'TK_CROSS' and base_score < cfg.get('high_quality_score_threshold', 74.0):
                 w_p, w_h = (1.0 - cfg.get('htf_conflict_dampen_weight', 0.15), cfg.get('htf_conflict_dampen_weight', 0.15)) if not htf_ok else (cfg.get('score_weight_primary', 0.75), cfg.get('score_weight_htf', 0.25))
                 base_score = (norm_primary_score * w_p) + (norm_htf_score * w_h)
            if not htf_ok and effective_mode == 'Adaptive':
                adaptive_penalties.append({'reason': 'HTF Conflict', 'value_pct': cfg.get('penalty_pct_htf_conflict', 15.0)})

        entry_price = self.price_data.get('close'); atr_val = self._safe_get(indicators, ['atr', 'values', 'atr'])
        
        is_late_entry = False
        if self._is_valid_number(entry_price) and self._is_valid_number(atr_val):
            is_late_entry = trigger_type == 'CLOUD_BREAKOUT' and abs(entry_price - ichi_values.get('senkou_a' if signal_direction == 'BUY' else 'senkou_b', entry_price)) > cfg.get('late_entry_atr_threshold', 1.2) * atr_val
        if is_late_entry:
            if effective_mode == 'Strict': self._log_final_decision("HOLD", "Strict Mode blocked by Late-Entry."); return None
            elif effective_mode == 'Adaptive':
                adaptive_penalties.append({'reason': 'Late Entry Risk', 'value_pct': cfg.get('penalty_pct_late_entry', 10.0)})
        
        final_score = base_score
        total_penalties = intrinsic_penalties + adaptive_penalties
        for p in total_penalties:
            final_score -= p.get('value_pct', 0.0)
        
        final_score = max(0.0, min(100.0, final_score))
        
        min_score_base = cfg.get('min_total_score_breakout_base') if trigger_type == "CLOUD_BREAKOUT" else cfg.get('min_total_score_base')
        min_score = min_score_base - 4.0 if adx_val < 18 else min_score_base - 2.0 if adx_val < cfg.get('market_regime_adx', 21) else min_score_base
        if final_score < min_score: self._log_final_decision("HOLD", f"Final score {final_score:.2f} < min {min_score}."); return None

        stop_loss = self._calculate_stop_loss(signal_direction, ichi_values, entry_price, atr_val, cfg)
        if not stop_loss: self._log_final_decision("HOLD", "Could not set SL."); return None
        
        rr_needed = 2.0 if final_score >= cfg.get('high_quality_score_threshold', 74.0) else cfg.get('min_rr_ratio', 1.6)
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        if not isinstance(risk_params, dict) or not risk_params: self._log_final_decision("HOLD", "R/R calc failed."); return None
        rr_val = risk_params.get("risk_reward_ratio")
        if not isinstance(rr_val, (int, float)) or rr_val < rr_needed: self._log_final_decision("HOLD", f"R/R {rr_val or 'N/A'} < min {rr_needed}."); return None

        self.last_signal_bar = current_bar
        signal_grade = self._grade_signal(final_score)
        narrative = self._generate_signal_narrative(direction, signal_grade, effective_mode, base_score, total_penalties, final_score)
        confirmations = {"total_score": round(final_score, 2), "signal_grade": signal_grade, "narrative": narrative, "htf_details": htf_details}
        self._log_final_decision(signal_direction, narrative)
        return {"direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations}

    def _evaluate_htf(self, trigger_type: str, direction: str, weights: Dict) -> Tuple[bool, str, float, List[Dict]]:
        if trigger_type == 'CLOUD_BREAKOUT':
            htf_ok = self._check_htf_breakout_context(direction)
            details = f"Context Check: {'Pass' if htf_ok else 'Fail'}"
            return htf_ok, details, 0.0, []
        else: # TK_CROSS
            norm_htf_score, htf_confirms, htf_penalties = self._score_and_normalize(direction, self.htf_analysis, weights)
            details = f"Score: {norm_htf_score:.2f}, Confirms: {','.join(htf_confirms)}, Penalties: {len(htf_penalties)}"
            htf_ichi = self.get_indicator('ichimoku', analysis_source=self.htf_analysis)
            htf_tk = str(self._safe_get(htf_ichi, ['analysis', 'tk_cross'], '')).lower()
            htf_dir = "BUY" if "bullish" in htf_tk else "SELL" if "bearish" in htf_tk else None
            
            htf_direction_ok = not (htf_dir and htf_dir != direction)
            htf_score_ok = norm_htf_score >= self.config.get('htf_min_score', 20.0)
            
            return htf_direction_ok and htf_score_ok, details, norm_htf_score, htf_penalties

    def _calculate_stop_loss(self, direction: str, ichi_vals: Dict, price: float, atr: float, cfg: Dict) -> Optional[float]:
        if not self._is_valid_number(price) or not self._is_valid_number(atr): return None
        sl_mode = str(cfg.get('sl_mode', 'hybrid')).lower()
        if sl_mode == 'hybrid':
            kijun = ichi_vals.get('kijun'); kumo = ichi_vals.get('senkou_b' if direction == 'BUY' else 'senkou_a')
            structural_sl = kumo if self._is_valid_number(kumo) else kijun
            if self._is_valid_number(structural_sl):
                max_dist = cfg.get('sl_hybrid_max_atr_mult', 2.0) * atr
                return (price - max_dist if direction == 'BUY' else price + max_dist) if abs(price - structural_sl) > max_dist else structural_sl
            return (price - (2.0 * atr) if direction == 'BUY' else price + (2.0 * atr))
        elif sl_mode == 'kumo': return ichi_vals.get('senkou_b' if direction == 'BUY' else 'senkou_a')
        elif sl_mode == 'kijun': return ichi_vals.get('kijun')
        return None
