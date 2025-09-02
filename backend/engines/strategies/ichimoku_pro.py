#backend/engines/strategies/ichimoku_pro.py
from __future__ import annotations
import logging
from typing import Dict, Any, Optional, List, Tuple, ClassVar
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class IchimokuHybridPro(BaseStrategy):
    """
    IchimokuHybridPro - (v9.0 - Asymmetric HTF Intelligence)
    -------------------------------------------------------------------------
    This major evolution introduces Asymmetric HTF Logic, resolving a key
    strategic conflict. The HTF logic now behaves differently and more
    intelligently depending on the trigger engine.

    🚀 KEY EVOLUTIONS in v9.0:
    1.  **Asymmetric HTF Logic:** HTF analysis is now engine-aware.
        - **Momentum Engine (TK Cross):** Retains the full, weighted scoring
          model to confirm trend depth.
        - **Structure Engine (Cloud Breakout):** Replaces full scoring with a
          new, faster "HTF Context Filter" to avoid the delayed confirmation trap.
    2.  **HTF Context Filter:** For breakouts, instead of a score, the strategy
        now checks if the HTF price is in a favorable context (e.g., above
        Kumo/Kijun for a BUY), increasing speed while maintaining safety.
    
    (All features from v8.0 are preserved)
    """
    strategy_name: str = "IchimokuHybridPro"
    
    default_config: ClassVar[Dict[str, Any]] = {
        # General Settings
        "market_regime_adx": 21,
        "min_rr_ratio": 1.8,

        # Stop-Loss & Risk Management
        "sl_mode": "hybrid",
        
        # --- SCORING ENGINE PROFILES ---
        "weights_trending": {
            "price_vs_kumo": 2, "tk_cross_strong": 3, "tk_cross_medium": 2,
            "future_kumo": 2, "chikou_free": 2, "chikou_near_free": 1,
            "kumo_twist": 1, "volume_spike": 1
        },
        "weights_ranging": {
            "price_vs_kumo": 1, "tk_cross_strong": 2, "tk_cross_medium": 2,
            "future_kumo": 1, "chikou_free": 1, "chikou_near_free": 1,
            "kumo_twist": 3, "volume_spike": 2
        },
        "weights_breakout": {
            "price_vs_kumo": 4, "chikou_free": 3, "future_kumo": 2,
            "volume_spike": 2, "kumo_twist": 1, "tk_cross_strong": 0,
            "tk_cross_medium": 0
        },

        # --- ASYMMETRIC HTF LOGIC ---
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        # For Momentum Engine (TK_CROSS)
        "score_weight_primary": 0.75,
        "score_weight_htf": 0.25,
        "primary_override_threshold": 80.0,
        "htf_conflict_dampen_weight": 0.15,
        # For Structure Engine (CLOUD_BREAKOUT)
        "htf_breakout_context_filter_enabled": True,
        "htf_breakout_context_levels": ["kumo", "kijun"], # Options: kumo, kijun

        # Dynamic Score Thresholds
        "min_total_score_base": 62.0,
        "min_total_score_breakout_base": 65.0,
    }

    def _indicator_ok(self, d: Optional[Dict]) -> bool:
        if not d: return False
        return bool(d.get('values')) or bool(d.get('analysis'))

    def _check_htf_breakout_context(self, direction: str) -> bool:
        """A lightweight filter for breakout signals, checking context not score."""
        if not self.htf_analysis:
            self._log_criteria("HTF Breakout Context", True, "HTF analysis not available, skipping filter.")
            return True # Fails open if no HTF data
            
        htf_ichi_data = self.get_indicator('ichimoku', analysis_source=self.htf_analysis)
        if not self._indicator_ok(htf_ichi_data):
            self._log_criteria("HTF Breakout Context", True, "HTF Ichimoku data invalid, skipping filter.")
            return True # Fails open

        htf_analysis = self._safe_get(htf_ichi_data, ['analysis'], {})
        htf_values = self._safe_get(htf_ichi_data, ['values'], {})
        htf_price = self._safe_get(self.htf_analysis, ['price_data', 'close'])
        
        if htf_price is None:
             self._log_criteria("HTF Breakout Context", True, "HTF price data missing, skipping filter.")
             return True

        context_ok = False
        reason = []
        
        check_levels = self.config.get("htf_breakout_context_levels", [])
        
        if direction == "BUY":
            if "kumo" in check_levels and htf_analysis.get('price_position') == "Above Kumo":
                context_ok = True
                reason.append("Price>HTF_Kumo")
            if not context_ok and "kijun" in check_levels:
                htf_kijun = htf_values.get('kijun')
                if htf_kijun is not None and htf_price > htf_kijun:
                    context_ok = True
                    reason.append("Price>HTF_Kijun")
        else: # SELL
            if "kumo" in check_levels and htf_analysis.get('price_position') == "Below Kumo":
                context_ok = True
                reason.append("Price<HTF_Kumo")
            if not context_ok and "kijun" in check_levels:
                htf_kijun = htf_values.get('kijun')
                if htf_kijun is not None and htf_price < htf_kijun:
                    context_ok = True
                    reason.append("Price<HTF_Kijun")
        
        final_reason = ", ".join(reason) if reason else "No favorable context found."
        self._log_criteria("HTF Breakout Context", context_ok, final_reason)
        return context_ok

    def _score_ichimoku(self, direction: str, analysis_data: Dict, weights: Dict) -> Tuple[int, List[str]]:
        score, confirmations = 0, []
        ichi_data = self.get_indicator('ichimoku', analysis_source=analysis_data)
        if not self._indicator_ok(ichi_data): return 0, []

        analysis = ichi_data.get('analysis', {})

        def check(name: str, weight_key: str, condition: bool):
            nonlocal score
            if condition:
                points = weights.get(weight_key, 0)
                if points > 0:
                    score += points
                    confirmations.append(name)
                    self._log_criteria(f"IchiComponent: {name}", True, f"Condition met, adding {points} points.")

        # Price vs Kumo, TK Cross, Future Kumo, Chikou, Kumo Twist...
        is_above_kumo = analysis.get('price_position') == "Above Kumo"
        is_below_kumo = analysis.get('price_position') == "Below Kumo"
        if direction == "BUY": check("Price>Kumo", 'price_vs_kumo', is_above_kumo)
        else: check("Price<Kumo", 'price_vs_kumo', is_below_kumo)

        tk_cross = str(analysis.get('tk_cross', "")).lower()
        is_strong = "strong" in tk_cross
        is_aligned = ("bullish" in tk_cross and direction == "BUY") or ("bearish" in tk_cross and direction == "SELL")
        if is_aligned:
            check("Strong_TK_Cross", 'tk_cross_strong', is_strong)
            check("Medium_TK_Cross", 'tk_cross_medium', not is_strong)
        
        future_kumo = analysis.get('future_kumo_direction', "")
        check("Future_Kumo_Aligned", 'future_kumo', (future_kumo == "Bullish" and direction == "BUY") or (future_kumo == "Bearish" and direction == "SELL"))

        chikou_status = analysis.get('chikou_status', "")
        check("Chikou_Free", 'chikou_free', ("Free (Bullish)" in chikou_status and direction == "BUY") or ("Free (Bearish)" in chikou_status and direction == "SELL"))

        kumo_twist = analysis.get('kumo_twist', "")
        check("Kumo_Twist_Aligned", 'kumo_twist', (kumo_twist == "Bullish Twist" and direction == "BUY") or (kumo_twist == "Bearish Twist" and direction == "SELL"))
        
        volume_data = self.get_indicator('volume', analysis_source=analysis_data) or {}
        vol_analysis = self._safe_get(volume_data, ['analysis'], {})
        is_volume_spike = vol_analysis.get('is_climactic_volume', False)
        check("Volume_Spike", 'volume_spike', is_volume_spike)
            
        return score, confirmations

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        if not self.price_data:
            self._log_final_decision("HOLD", "No price data available."); return None

        required_names = ['ichimoku', 'adx', 'atr', 'volume']
        indicators = {name: self.get_indicator(name) for name in required_names}
        
        if any(not self._indicator_ok(data) for data in indicators.values()):
            missing = [name for name, data in indicators.items() if not self._indicator_ok(data)]
            self._log_final_decision("HOLD", f"Missing or invalid indicator data for: {', '.join(missing)}"); return None

        # --- 1. Determine Signal Trigger & Select Engine ---
        ichi_analysis = self._safe_get(indicators, ['ichimoku', 'analysis'], {})
        ichi_values = self._safe_get(indicators, ['ichimoku', 'values'], {})
        signal_direction, trigger_type = None, None
        
        tk_cross = str(ichi_analysis.get('tk_cross', "")).lower()
        if "bullish" in tk_cross: signal_direction, trigger_type = "BUY", "TK_CROSS"
        elif "bearish" in tk_cross: signal_direction, trigger_type = "SELL", "TK_CROSS"
        
        if trigger_type is None:
            price_pos, senkou_a, senkou_b = ichi_analysis.get('price_position'), ichi_values.get('senkou_a'), ichi_values.get('senkou_b')
            if price_pos == "Above Kumo" and senkou_a is not None and senkou_b is not None and senkou_a > senkou_b:
                signal_direction, trigger_type = "BUY", "CLOUD_BREAKOUT"
            elif price_pos == "Below Kumo" and senkou_a is not None and senkou_b is not None and senkou_a < senkou_b:
                signal_direction, trigger_type = "SELL", "CLOUD_BREAKOUT"

        if signal_direction is None:
            self._log_final_decision("HOLD", "No primary trigger found."); return None
        self._log_criteria("Primary Trigger", True, f"'{trigger_type}' detected. Signal direction: '{signal_direction}'.")
        
        # --- 2. Configure Active Engine & Dynamic Score Threshold ---
        adx_val = self._safe_get(indicators, ['adx', 'values', 'adx'], 0.0)
        
        if trigger_type == 'TK_CROSS':
            mr_threshold = float(cfg.get('market_regime_adx', 21))
            market_regime = "TRENDING" if adx_val > mr_threshold else "RANGING"
            active_weights = cfg.get('weights_trending') if market_regime == "TRENDING" else cfg.get('weights_ranging')
            min_score_base = float(cfg.get('min_total_score_base', 62.0))
            self._log_criteria("Engine Activated", True, f"Momentum Engine. Regime='{market_regime}' (ADX={adx_val:.2f})")
        else: # CLOUD_BREAKOUT
            market_regime = "BREAKOUT"
            active_weights = cfg.get('weights_breakout', {})
            min_score_base = float(cfg.get('min_total_score_breakout_base', 65.0))
            self._log_criteria("Engine Activated", True, "Structure Engine.")

        min_score = min_score_base - 4.0 if adx_val < 18 else min_score_base - 2.0 if adx_val < cfg.get('market_regime_adx', 21) else min_score_base
        self._log_criteria("Dynamic Min Score", True, f"Minimum score set to {min_score} based on ADX.")

        # --- 3. Calculate Scores & Apply Asymmetric HTF Logic ---
        primary_score, primary_confirms = self._score_ichimoku(signal_direction, self.analysis, active_weights)
        max_possible_score = sum(active_weights.values())
        norm_primary_score = round((primary_score / max_possible_score) * 100, 2) if max_possible_score > 0 else 0.0
        
        final_score = norm_primary_score
        htf_details = "N/A"
        htf_enabled = cfg.get('htf_confirmation_enabled', True) and bool(self.htf_analysis)

        # 🚀 ASYMMETRIC HTF LOGIC v9.0 🚀
        if htf_enabled and trigger_type == 'TK_CROSS':
            htf_score, htf_confirms = self._score_ichimoku(signal_direction, self.htf_analysis, active_weights)
            norm_htf_score = round((htf_score / max_possible_score) * 100, 2) if max_possible_score > 0 else 0.0
            
            use_weighted_htf = True
            if norm_primary_score >= cfg.get('primary_override_threshold', 80.0):
                use_weighted_htf = False
                htf_details = f"N/A (Primary Score {norm_primary_score:.2f} > Override Threshold)"
            
            if use_weighted_htf:
                w_primary, w_htf = cfg.get('score_weight_primary', 0.75), cfg.get('score_weight_htf', 0.25)
                # Check for conflict
                htf_ichi_analysis = self._safe_get(self.get_indicator('ichimoku', analysis_source=self.htf_analysis), ['analysis'], {})
                htf_tk_cross = str(htf_ichi_analysis.get('tk_cross', "")).lower()
                htf_direction = "BUY" if "bullish" in htf_tk_cross else "SELL" if "bearish" in htf_tk_cross else None
                if htf_direction and htf_direction != signal_direction:
                    self._log_criteria("HTF Logic", False, f"Conflict detected! PT is {signal_direction}, HTF is {htf_direction}. Dampening HTF weight.")
                    w_htf = cfg.get('htf_conflict_dampen_weight', 0.15); w_primary = 1.0 - w_htf
                
                final_score = (norm_primary_score * w_primary) + (norm_htf_score * w_htf)
                htf_details = f"{htf_score}/{max_possible_score} ({','.join(htf_confirms)})"
        
        log_score_details = f"Final Score={final_score:.2f} (Primary: {norm_primary_score:.0f}%)"
        if 'norm_htf_score' in locals() and use_weighted_htf:
            log_score_details = f"Weighted Score={final_score:.2f} (Primary: {norm_primary_score:.0f}%*{w_primary*100}%, HTF: {norm_htf_score:.0f}%*{w_htf*100}%)"
            
        score_is_ok = final_score >= min_score
        self._log_criteria("Total Score Check", score_is_ok, f"{log_score_details} vs min={min_score}")
        if not score_is_ok:
            self._log_final_decision("HOLD", f"Final score {final_score:.2f} < minimum {min_score}."); return None

        # --- 4. Final Gates: HTF Context & Risk/Reward ---
        if htf_enabled and trigger_type == 'CLOUD_BREAKOUT' and cfg.get('htf_breakout_context_filter_enabled', True):
            if not self._check_htf_breakout_context(signal_direction):
                self._log_final_decision("HOLD", "HTF context filter failed for breakout signal."); return None

        # R/R Calculation
        entry_price = self.price_data.get('close')
        if entry_price is None:
            self._log_final_decision("HOLD", "Could not determine entry price."); return None

        # ... [Stop-Loss logic remains unchanged] ...
        sl_mode = str(cfg.get('sl_mode', 'hybrid')).lower()
        atr_val = (indicators['atr']['values'] or {}).get('atr')
        stop_loss: Optional[float] = None
        if sl_mode == 'hybrid' and atr_val:
            kijun_sl = ichi_values.get('kijun'); kumo_sl = ichi_values.get('senkou_b') if signal_direction == 'BUY' else ichi_values.get('senkou_a')
            structural_sl = kumo_sl if kumo_sl is not None else kijun_sl
            if structural_sl and abs(entry_price - structural_sl) > 2.5 * atr_val:
                if signal_direction == 'BUY': stop_loss = max(kijun_sl or (entry_price - 2 * atr_val), entry_price - 2 * atr_val)
                else: stop_loss = min(kijun_sl or (entry_price + 2 * atr_val), entry_price + 2 * atr_val)
            else: stop_loss = structural_sl
        else:
            stop_loss = ichi_values.get('senkou_b') if sl_mode == 'kumo' else ichi_values.get('kijun')
        
        if stop_loss is None:
            self._log_final_decision("HOLD", "Could not set Stop Loss."); return None

        rr_needed = 2.0 if norm_primary_score >= 80.0 else cfg.get('min_rr_ratio', 1.8)
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        rr_val = (risk_params or {}).get("risk_reward_ratio")
        rr_is_ok = rr_val is not None and rr_val >= rr_needed
        rr_display = f"{rr_val:.2f}" if rr_val is not None else "N/A"
        
        self._log_criteria("Risk/Reward Check", rr_is_ok, f"R/R={rr_display} vs min required={rr_needed} (stepped)")
        if not rr_is_ok:
            self._log_final_decision("HOLD", "Risk/Reward ratio is too low."); return None

        # --- 5. Final Confirmation ---
        confirmations = {
            "total_score": round(final_score, 2),
            "trigger_type": trigger_type,
            "market_regime": market_regime,
            "primary_score_details": f"{primary_score}/{max_possible_score} ({','.join(primary_confirms)})",
            "htf_score_details": htf_details,
            "rr_check": f"Passed (R/R={rr_display}, Needed={rr_needed})"
        }
        
        self._log_final_decision(signal_direction, f"All criteria met. Ichimoku Hybrid Pro ({trigger_type}) signal confirmed.")
        return { "direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations }

