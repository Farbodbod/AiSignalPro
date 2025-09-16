# backend/engines/strategies/ichimoku_pro.py - (v25.0 - The Final OHRE v3.0 Integration)

from __future__ import annotations
import logging
import pandas as pd
from typing import Dict, Any, Optional, List, Tuple, ClassVar

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class IchimokuHybridPro(BaseStrategy):
    """
    IchimokuHybridPro - (v25.0 - The Final OHRE v3.0 Integration)
    -------------------------------------------------------------------------
    This version completes the full architectural harmonization with BaseStrategy v25.0.
    The strategy's powerful, multi-trigger signal engine is now perfectly paired with
    the new OHRE v3.0 ("The Maestro Engine"). All internal, custom SL logic has been
    removed, fully delegating the responsibility of finding the optimal structural SL
    and calculating quantum targets to the BaseStrategy. This simplifies the strategy's
    code while significantly upgrading its risk management capabilities to the project's
    gold standard.
    """
    strategy_name: str = "IchimokuHybridPro"
    
    # --- Default config cleaned of all obsolete risk parameters ---
    default_config: ClassVar[Dict[str, Any]] = {
      "operation_mode": "Regime-Aware",
      "market_regime_adx_percentile": 70.0,
      "penalty_pct_htf_conflict": 35.0,
      "min_total_score_base": 68.0,
      "min_total_score_breakout_base": 70.0,
      "min_score_pullback_base": 75.0,
      "min_score_reversal_base": 72.0,

      "weights_trending": { "price_vs_kumo": 2, "tk_cross_strong": 3, "tk_cross_medium": 2, "future_kumo": 1, "chikou_free": 2, "kumo_twist": 1, "volume_spike": 2, "volatility_filter": -5, "leading_timing_confirm": 2, "macd_aligned": 2 },
      "weights_ranging": { "price_vs_kumo": 1, "tk_cross_strong": 3, "tk_cross_medium": 2, "future_kumo": 1, "chikou_free": 2, "kumo_twist": 4, "volume_spike": 2, "volatility_filter": -5, "leading_timing_confirm": 2, "macd_aligned": 2 },
      "weights_breakout": { "price_vs_kumo": 4, "chikou_free": 3, "future_kumo": 1, "volume_spike": 3, "kumo_twist": 1, "macd_aligned": 3 },
      "weights_reversal": { "kumo_rejection_candle": 5, "volume_spike": 3, "future_kumo_aligned": 2, "macd_aligned": 3 },
      
      "weights_pullback": { "pullback_to_key_level": 5, "chikou_free": 3, "future_kumo": 2, "volume_spike": 3, "leading_timing_confirm": 2, "macd_aligned": 3 },
      "pullback_config": { "enabled": True, "candle_reliability": "Medium" },

      "htf_quality_scoring": {
        "enabled": True,
        "weights_htf": { "price_vs_kumo": 4, "chikou_free": 3, "future_kumo_aligned": 2, "supertrend_aligned": 3, "adx_strong": 2, "macd_aligned": 2 },
        "min_score_levels": { "weak": 30.0, "normal": 50.0, "strong": 70.0 },
        "strict_mode_requires_quality": "normal",
        "adx_min_percentile_for_htf": 75.0
      },
      
      "timing_and_exhaustion_engine": { "enabled": True, "timing_confirm_enabled": True, "timing_mode": "dynamic", "timing_apply_to_tk_cross": True, "timing_apply_to_breakout": False, "timing_dynamic_rsi_lookback": 100, "timing_dynamic_rsi_buy_percentile": 30, "timing_dynamic_rsi_sell_percentile": 70, "exhaustion_shield_enabled": True, "exhaustion_mode": "dynamic", "exhaustion_dynamic_rsi_lookback": 100, "exhaustion_dynamic_overbought_percentile": 90, "exhaustion_dynamic_oversold_percentile": 10 },
      "kumo_reversal_engine": { "enabled": True, "min_reliability": "Medium" },
      "signal_grading_thresholds": { "strong": 80.0, "normal": 60.0 },
      "high_quality_score_threshold": 74.0, "min_rr_ratio": 1.5,
      "volume_z_relax_threshold": 1.5,
      "cooldown_bars": 3, "outlier_candle_shield": True, "outlier_atr_mult": 3.5,
      "late_entry_atr_threshold": 1.2,
      "htf_confirmation_enabled": True, "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
      "score_weight_primary": 0.75, "score_weight_htf": 0.25,
      "htf_conflict_dampen_weight": 0.15, "htf_breakout_context_filter_enabled": True,
      "htf_breakout_context_levels": ["kumo", "kijun"]
    }

    # --- Helper methods integral to the strategy's unique logic (Unchanged) ---
    def _indicator_ok(self, d: Optional[Dict]) -> bool:
        # ... (code remains unchanged)
        return isinstance(d, dict) and (d.get('values') or d.get('analysis'))

    def _grade_signal(self, score: float) -> str:
        # ... (code remains unchanged)
        thresholds = self.config.get('signal_grading_thresholds', {})
        if score >= thresholds.get('strong', 80.0): return "Strong"
        if score >= thresholds.get('normal', 60.0): return "Normal"
        return "Weak"

    def _generate_signal_narrative(self, direction: str, grade: str, mode: str, base_score: float, penalties: List[Dict], final_score: float, htf_details: str, htf_grade: str) -> str:
        # ... (code remains unchanged)
        base = f"{direction} signal ({mode} Mode, {grade} grade)"
        score_str = f"Base Score: {base_score:.2f}"
        if penalties: penalty_parts = [f"-{p['value_pct']:.2f}% ({p['reason']})" for p in penalties]; penalties_str = "Penalties: " + " , ".join(penalty_parts)
        else: penalties_str = ""
        htf_str = f"HTF Quality: {htf_grade} ({htf_details})" if htf_details != "N/A" else ""
        final_str = f"Final: {final_score:.2f}"
        parts = [base, score_str, htf_str, penalties_str, final_str]
        return ". ".join(filter(None, parts))

    def _check_htf_breakout_context(self, direction: str) -> bool:
        # ... (code remains unchanged)
        if not self.htf_analysis: return True
        htf_ichi_data = self.get_indicator('ichimoku', analysis_source=self.htf_analysis)
        if not self._indicator_ok(htf_ichi_data): return True
        htf_analysis = self._safe_get(htf_ichi_data, ['analysis'], {}); htf_values = self._safe_get(htf_ichi_data, ['values'], {})
        htf_price = self._safe_get(self.htf_analysis, ['price_data', 'close'])
        if not self._is_valid_number(htf_price): return True
        context_ok = False; check_levels = self.config.get('htf_breakout_context_levels', []); htf_kijun = htf_values.get('kijun')
        if direction == "BUY": context_ok = ("kumo" in check_levels and htf_analysis.get('price_position') == "Above Kumo") or ("kijun" in check_levels and self._is_valid_number(htf_kijun) and htf_price > htf_kijun)
        else: context_ok = ("kumo" in check_levels and htf_analysis.get('price_position') == "Below Kumo") or ("kijun" in check_levels and self._is_valid_number(htf_kijun) and htf_price < htf_kijun)
        return context_ok

    def _score_and_normalize(self, direction: str, analysis_data: Dict, weights: Dict, trigger_type: str) -> Tuple[float, List[str], List[Dict]]:
        # ... (code remains unchanged)
        self._log_criteria(f"Path Check: Scoring Engine", True, f"Calculating base score for trigger '{trigger_type}'.")
        positive_score, confirmations, penalties = 0, [], []
        positive_weights = {k: v for k, v in weights.items() if v > 0}
        penalty_weights = {k: v for k, v in weights.items() if v < 0}
        max_positive_score = sum(positive_weights.values())
        component_results = {}
        def check(name: str, weight_key: str, condition: bool):
            nonlocal positive_score, confirmations
            component_results[name] = (condition, weight_key)
            if condition and weight_key in positive_weights:
                positive_score += positive_weights[weight_key]
                confirmations.append(name)
        ichi_data = self.get_indicator('ichimoku', analysis_source=analysis_data)
        if not self._indicator_ok(ichi_data): return 0.0, [], []
        analysis = ichi_data.get('analysis', {})
        is_above_kumo = analysis.get('price_position') == "Above Kumo"
        is_below_kumo = analysis.get('price_position') == "Below Kumo"
        check("Price>Kumo", 'price_vs_kumo', (direction == "BUY" and is_above_kumo) or (direction == "SELL" and is_below_kumo))
        tk_cross = str(analysis.get('tk_cross', "")).lower()
        is_strong_cross = "strong" in tk_cross
        is_tk_aligned = ("bullish" in tk_cross and direction == "BUY") or ("bearish" in tk_cross and direction == "SELL")
        if is_tk_aligned:
            check("Strong TK Cross", 'tk_cross_strong', is_strong_cross)
            check("Medium TK Cross", 'tk_cross_medium', not is_strong_cross)
        future_kumo_raw = str(analysis.get('future_kumo_direction', '')).strip().lower()
        future_kumo_mapped = "BUY" if future_kumo_raw == 'bullish' else "SELL" if future_kumo_raw == 'bearish' else None
        check("Future Kumo Aligned", 'future_kumo', future_kumo_mapped is not None and future_kumo_mapped == direction)
        chikou_status = analysis.get('chikou_status', "")
        check("Chikou Free", 'chikou_free', "Free" in chikou_status and (("Bullish" in chikou_status and direction == "BUY") or ("Bearish" in chikou_status and direction == "SELL")))
        kumo_twist = analysis.get('kumo_twist', "")
        check("Kumo Twist Aligned", 'kumo_twist', (kumo_twist == "Bullish Twist" and direction == "BUY") or (kumo_twist == "Bearish Twist" and direction == "SELL"))
        volume_data = self.get_indicator('volume', analysis_source=analysis_data)
        is_climactic = self._safe_get(volume_data, ['analysis', 'is_climactic_volume'], False)
        zscore = self._safe_get(volume_data, ['values', 'z_score'])
        is_z_spike = self._is_valid_number(zscore) and zscore >= self.config.get('volume_z_relax_threshold', 1.5)
        check("Volume Spike", 'volume_spike', is_climactic or is_z_spike)
        macd_data = self.get_indicator('macd', analysis_source=analysis_data)
        macd_context = self._safe_get(macd_data, ['analysis', 'context'], {})
        macd_ok = (direction == "BUY" and macd_context.get('momentum') == "Increasing" and macd_context.get('trend') == "Uptrend") or \
                  (direction == "SELL" and macd_context.get('momentum') == "Increasing" and macd_context.get('trend') == "Downtrend")
        check("MACD Aligned", 'macd_aligned', macd_ok)
        if trigger_type == 'KUMO_REVERSAL': check("Kumo Rejection Candle", 'kumo_rejection_candle', True)
        if trigger_type == 'PULLBACK': check("Pullback to Key Level", 'pullback_to_key_level', True)
        engine_cfg = self.config.get('timing_and_exhaustion_engine', {})
        apply_timing = 'timing_apply_to_tk_cross' if trigger_type in ['TK_CROSS', 'PULLBACK'] else 'timing_apply_to_breakout'
        if engine_cfg.get('enabled', True) and engine_cfg.get('timing_confirm_enabled', True) and engine_cfg.get(apply_timing, False):
            is_timing_ok = not self._is_trend_exhausted_dynamic(
                direction=direction, 
                rsi_lookback=engine_cfg.get('timing_dynamic_rsi_lookback', 100), 
                rsi_buy_percentile=engine_cfg.get('timing_dynamic_rsi_sell_percentile', 70), 
                rsi_sell_percentile=engine_cfg.get('timing_dynamic_rsi_buy_percentile', 30)
            )
            check("Timing Confirmed (Dynamic)", "leading_timing_confirm", is_timing_ok)
        for key, raw_points in penalty_weights.items():
            vol_state = str(self._safe_get(self.get_indicator('keltner_channel', analysis_source=analysis_data), ['analysis', 'volatility_state'], '')).lower()
            if key == 'volatility_filter' and vol_state in ('squeeze', 'compression', 'low'):
                penalties.append({'reason': f"Volatility Filter ({vol_state})", 'value_pct': abs(raw_points)})
        normalized_score = round((positive_score / max_positive_score) * 100, 2) if max_positive_score > 0 else 0.0
        passed_confirmations = confirmations
        failed_confirmations = [name for name, (status, w_key) in component_results.items() if not status and w_key in positive_weights]
        log_msg = (f"Trigger: '{trigger_type}', Score: {normalized_score:.2f}. Confirms: {passed_confirmations}. Fails: {failed_confirmations}.")
        self._log_criteria("Scoring Result", normalized_score > 0, log_msg)
        return normalized_score, confirmations, penalties

    def _evaluate_htf(self, trigger_type: str, direction: str) -> Tuple[bool, str, float, List[Dict], str]:
        # ... (code remains unchanged)
        htf_cfg = self.config.get('htf_quality_scoring', {})
        if not htf_cfg.get('enabled', True) or not self.htf_analysis: 
            return True, "Disabled", 100.0, [], "N/A"
        htf_weights = htf_cfg.get('weights_htf', {}).copy()
        if trigger_type == 'KUMO_REVERSAL' and 'price_vs_kumo' in htf_weights:
            del htf_weights['price_vs_kumo']
        max_score = sum(htf_weights.values())
        current_score = 0
        confirmations = []
        component_results = {}
        def check(name: str, weight_key: str, condition: bool):
            nonlocal current_score
            component_results[name] = (condition, weight_key)
            if condition and weight_key in htf_weights:
                current_score += htf_weights[weight_key]
                confirmations.append(name)
        htf_ichi = self.get_indicator('ichimoku', analysis_source=self.htf_analysis)
        htf_adx = self.get_indicator('adx', analysis_source=self.htf_analysis)
        htf_st = self.get_indicator('supertrend', analysis_source=self.htf_analysis)
        htf_macd = self.get_indicator('macd', analysis_source=self.htf_analysis)
        ichi_analysis = self._safe_get(htf_ichi, ['analysis'], {})
        ichi_dir_is_aligned = (self._safe_get(ichi_analysis, ['trend_score'], 0) > 0 and direction == "BUY") or \
                              (self._safe_get(ichi_analysis, ['trend_score'], 0) < 0 and direction == "SELL")
        price_pos_ok = self._safe_get(ichi_analysis, ['price_position']) not in ["Inside Kumo"] and ichi_dir_is_aligned
        check("HTF Price vs Kumo", 'price_vs_kumo', price_pos_ok)
        chikou_ok = "Free" in self._safe_get(ichi_analysis, ['chikou_status'], '')
        check("HTF Chikou Free", 'chikou_free', chikou_ok)
        future_kumo_raw = str(self._safe_get(ichi_analysis, ['future_kumo_direction'], '')).strip().lower()
        future_kumo_mapped = "BUY" if future_kumo_raw == 'bullish' else "SELL" if future_kumo_raw == 'bearish' else None
        future_kumo_ok = future_kumo_mapped is not None and future_kumo_mapped == direction
        check("HTF Future Kumo", 'future_kumo_aligned', future_kumo_ok)
        adx_percentile_htf = self._safe_get(htf_adx, ['analysis', 'adx_percentile'])
        min_percentile_htf = htf_cfg.get('adx_min_percentile_for_htf', 75.0)
        adx_ok = self._is_valid_number(adx_percentile_htf) and adx_percentile_htf >= min_percentile_htf
        check("HTF ADX Strong (Adaptive)", 'adx_strong', adx_ok)
        st_trend = self._safe_get(htf_st, ['analysis', 'trend'], '').upper()
        st_ok = st_trend == direction
        check("HTF SuperTrend Aligned", 'supertrend_aligned', st_ok)
        macd_context = self._safe_get(htf_macd, ['analysis', 'context'], {})
        macd_ok = macd_context.get('trend', '').upper() == direction and macd_context.get('momentum') == "Increasing"
        check("HTF MACD Aligned", 'macd_aligned', macd_ok)
        norm_htf_score = round((current_score / max_score) * 100, 2) if max_score > 0 else 0
        levels = htf_cfg.get('min_score_levels', {}); grade = "Fail"
        if norm_htf_score >= levels.get('strong', 70.0): grade = "Strong"
        elif norm_htf_score >= levels.get('normal', 50.0): grade = "Normal"
        elif norm_htf_score >= levels.get('weak', 30.0): grade = "Weak"
        required_quality = htf_cfg.get('strict_mode_requires_quality', 'normal')
        quality_map = {"Fail": 0, "Weak": 1, "Normal": 2, "Strong": 3}
        is_quality_ok = quality_map.get(grade, 0) >= quality_map.get(required_quality, 2)
        passed_confirmations = confirmations
        failed_confirmations = [name for name, (status, w_key) in component_results.items() if not status and w_key in htf_weights]
        log_msg = (f"Score: {norm_htf_score:.2f}, Grade: {grade}. Confirms: {passed_confirmations}. Fails: {failed_confirmations}.")
        self._log_criteria("HTF Evaluation Result", is_quality_ok, log_msg)
        details_for_narrative = f"Score: {norm_htf_score:.2f}, Grade: {grade}"
        return is_quality_ok, details_for_narrative, norm_htf_score, [], grade

    # --- Custom SL logic is now removed as OHRE v3.0 handles it ---
    # def _calculate_stop_loss(...)
    
    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        
        if not self.price_data or not isinstance(self.df, pd.DataFrame) or self.df.empty: return None
        if (len(self.df) - 1 - getattr(self, "last_signal_bar", -10**9)) < cfg.get('cooldown_bars', 3): return None
        
        # UPGRADED: Added dependencies for OHRE v3.0
        required = ['ichimoku', 'adx', 'atr', 'volume', 'keltner_channel', 'rsi', 'patterns', 'macd', 'supertrend', 'pivots', 'structure']
        indicators = {name: self.get_indicator(name) for name in required}
        if any(not self._indicator_ok(data) for data in indicators.values()): return None
        if cfg.get('outlier_candle_shield', True) and self._is_outlier_candle(atr_multiplier=cfg.get('outlier_atr_mult', 3.5)): return None

        # --- The multi-trigger signal detection logic is 100% preserved ---
        potential_signals = []
        ichi_analysis = self._safe_get(indicators, ['ichimoku', 'analysis'], {}); ichi_values = self._safe_get(indicators, ['ichimoku', 'values'], {})
        price_pos = ichi_analysis.get('price_position', '')
        pullback_cfg = cfg.get('pullback_config', {})
        if pullback_cfg.get('enabled', True) and price_pos in ["Above Kumo", "Below Kumo"]:
            direction = "BUY" if price_pos == "Above Kumo" else "SELL"
            price_low, price_high = self.price_data.get('low'), self.price_data.get('high')
            kijun = ichi_values.get('kijun')
            is_pullback = (direction == "BUY" and self._is_valid_number(price_low, kijun) and price_low <= kijun) or \
                          (direction == "SELL" and self._is_valid_number(price_high, kijun) and price_high >= kijun)
            if is_pullback and self._get_candlestick_confirmation(direction, min_reliability=pullback_cfg.get('candle_reliability', 'Medium')):
                score, confirms, penalties = self._score_and_normalize(direction, self.analysis, cfg.get('weights_pullback', {}), "PULLBACK")
                potential_signals.append({'score': score, 'direction': direction, 'trigger': 'PULLBACK', 'confirms': confirms, 'penalties': penalties})
        tk_cross = str(ichi_analysis.get('tk_cross', "")).lower()
        tk_cross_direction = "BUY" if "bullish" in tk_cross else "SELL" if "bearish" in tk_cross else None
        if tk_cross_direction:
            adx_data = indicators.get('adx')
            adx_percentile = self._safe_get(adx_data, ['analysis', 'adx_percentile'], 0.0)
            regime = "TRENDING" if adx_percentile >= cfg.get('market_regime_adx_percentile', 70.0) else "RANGING"
            if price_pos == "Inside Kumo": regime = "RANGING"
            weights = cfg.get('weights_trending' if regime == "TRENDING" else 'weights_ranging', {})
            score, confirms, penalties = self._score_and_normalize(tk_cross_direction, self.analysis, weights, "TK_CROSS")
            potential_signals.append({'score': score, 'direction': tk_cross_direction, 'trigger': 'TK_CROSS', 'regime': regime, 'confirms': confirms, 'penalties': penalties})
        s_a, s_b = ichi_values.get('senkou_a'), ichi_values.get('senkou_b')
        breakout_direction = "BUY" if price_pos == "Above Kumo" and self._is_valid_number(s_a, s_b) and s_a > s_b else "SELL" if price_pos == "Below Kumo" and self._is_valid_number(s_a, s_b) and s_a < s_b else None
        if breakout_direction:
            score, confirms, penalties = self._score_and_normalize(breakout_direction, self.analysis, cfg.get('weights_breakout', {}), "CLOUD_BREAKOUT")
            potential_signals.append({'score': score, 'direction': breakout_direction, 'trigger': 'CLOUD_BREAKOUT', 'regime': 'BREAKOUT', 'confirms': confirms, 'penalties': penalties})
        reversal_cfg = cfg.get('kumo_reversal_engine', {})
        if reversal_cfg.get('enabled', False) and price_pos == "Inside Kumo":
            for d in ["BUY", "SELL"]:
                if self._get_candlestick_confirmation(direction=d, min_reliability=reversal_cfg.get('min_reliability', 'Medium')):
                    score, confirms, penalties = self._score_and_normalize(d, self.analysis, cfg.get('weights_reversal', {}), "KUMO_REVERSAL")
                    potential_signals.append({'score': score, 'direction': d, 'trigger': 'KUMO_REVERSAL', 'regime': 'REVERSAL', 'confirms': confirms, 'penalties': penalties})

        if not potential_signals: self._log_final_decision("HOLD", "No actionable trigger found."); return None
        
        best_signal = max(potential_signals, key=lambda x: x['score'])
        signal_direction, trigger_type, market_regime, base_score, _, intrinsic_penalties = best_signal['direction'], best_signal['trigger'], best_signal.get('regime', 'PULLBACK'), best_signal['score'], best_signal['confirms'], best_signal['penalties']
        engine_cfg = cfg.get('timing_and_exhaustion_engine', {})
        if engine_cfg.get('enabled', True) and engine_cfg.get('exhaustion_shield_enabled', True):
            if self._is_trend_exhausted_dynamic(direction=signal_direction, rsi_lookback=engine_cfg.get('exhaustion_dynamic_rsi_lookback', 100), rsi_buy_percentile=engine_cfg.get('exhaustion_dynamic_overbought_percentile', 90), rsi_sell_percentile=engine_cfg.get('exhaustion_dynamic_oversold_percentile', 10)):
                self._log_final_decision("HOLD", "Signal blocked by Trend Exhaustion Shield."); return None
        operation_mode = cfg.get('operation_mode', 'Regime-Aware'); effective_mode = 'Strict' if operation_mode == 'Regime-Aware' and market_regime in ['TRENDING','BREAKOUT','PULLBACK'] else 'Adaptive'
        is_htf_ok, htf_details, _, _, htf_quality_grade = self._evaluate_htf(trigger_type, signal_direction)
        adaptive_penalties = []
        if not is_htf_ok:
            if effective_mode == 'Strict': self._log_final_decision("HOLD", f"Strict Mode blocked by HTF failure ({htf_details})."); return None
            adaptive_penalties.append({'reason': 'HTF Conflict', 'value_pct': cfg.get('penalty_pct_htf_conflict', 35.0)})
        final_score = base_score
        total_penalties = intrinsic_penalties + adaptive_penalties
        for p in total_penalties: final_score -= p.get('value_pct', 0.0)
        final_score = max(0.0, min(100.0, final_score))
        min_score_map = {'PULLBACK': 'min_score_pullback_base', 'CLOUD_BREAKOUT': 'min_total_score_breakout_base', 'KUMO_REVERSAL': 'min_score_reversal_base'}
        min_score_key = min_score_map.get(trigger_type, 'min_total_score_base')
        min_score = cfg.get(min_score_key, 68.0)
        if final_score < min_score: self._log_final_decision("HOLD", f"Final score {final_score:.2f} is below minimum required {min_score:.2f}."); return None
        
        # --- ✅ RISK MANAGEMENT UPGRADE ---
        entry_price = self.price_data.get('close')
        
        # 1. Preserve the dynamic R:R logic by setting an override for the OHRE
        rr_needed = 2.0 if final_score >= cfg.get('high_quality_score_threshold', 74.0) else cfg.get('min_rr_ratio', 1.5)
        self.config['override_min_rr_ratio'] = rr_needed
        
        # 2. Delegate fully to the OHRE v3.0
        risk_params = self._orchestrate_static_risk(
            direction=signal_direction,
            entry_price=entry_price
        )

        # 3. Clean up the temporary override
        self.config.pop('override_min_rr_ratio', None)

        if not risk_params: 
            self._log_final_decision("HOLD", f"OHRE v3.0 failed to generate a valid risk plan (min R:R needed: {rr_needed})."); return None

        # --- Final signal construction is preserved ---
        self.last_signal_bar = len(self.df) - 1
        signal_grade = self._grade_signal(final_score)
        narrative = self._generate_signal_narrative(signal_direction, signal_grade, effective_mode, base_score, total_penalties, final_score, htf_details, htf_quality_grade)
        confirmations = {"total_score": round(final_score, 2), "signal_grade": signal_grade, "narrative": narrative}
        
        self._log_final_decision(signal_direction, narrative)
        return {"direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations}
