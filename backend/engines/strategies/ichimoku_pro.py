# backend/engines/strategies/ichimoku_hybrid_pro.py (v6.1 - Robustness Patches)

from __future__ import annotations
import logging
from typing import Dict, Any, Optional, List, Tuple, ClassVar
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class IchimokuHybridPro(BaseStrategy):
    """
    IchimokuHybridPro - (v6.1 - Robustness Patches)
    -------------------------------------------------------------------------
    This version builds upon the dynamic engine of v6.0 by introducing critical
    robustness patches identified during a deep code review. It enhances stability
    and future-proofing without altering the core trading logic.

    Key enhancements from v6.0 retained:
    1.  Multi-Level Scoring (Strong/Medium TK Cross)
    2.  Expanded Triggers (Cloud Breakout Structure)
    3.  Dynamic Score Threshold (ADX-based)
    4.  Intelligent HTF Logic (Override & Conflict Dampening)
    5.  Hybrid Stop-Loss (Kumo/Kijun/ATR)
    6.  Stepped R/R Ratio
    7.  Z-Score Volume Analysis

    ✅ New in v6.1:
    8.  **Robustness Patches:** Includes critical fixes for indicator validation
        (correctly handling analysis-only indicators) and robust data access for
        volume Z-score, ensuring higher stability and preventing silent failures.
    """
    strategy_name: str = "IchimokuHybridPro"
    
    default_config: ClassVar[Dict[str, Any]] = {
        # General Settings
        "market_regime_adx": 21,
        "min_rr_ratio": 1.8,  # Base R/R, becomes dynamic (2.0) for high-conviction signals

        # Stop-Loss & Risk Management
        "sl_mode": "hybrid",  # Options: 'kumo', 'kijun', 'hybrid'
        
        # Scoring Weights
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

        # Multi-Timeframe (HTF) Logic
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "score_weight_primary": 0.75,
        "score_weight_htf": 0.25,
        "primary_override_threshold": 80.0,
        "htf_conflict_dampen_weight": 0.15,

        # Dynamic Score Threshold
        "min_total_score_base": 62.0,

        # Volume Analysis
        "volume_z_lookback": 80,
        "volume_z_threshold": 2.0,
    }

    def _indicator_ok(self, d: Optional[Dict]) -> bool:
        """Helper to robustly check if an indicator has valid data."""
        if not d:
            return False
        # An indicator is valid if it has EITHER a 'values' or 'analysis' key with content.
        return bool(d.get('values')) or bool(d.get('analysis'))

    def _score_ichimoku(self, direction: str, analysis_data: Dict, weights: Dict) -> Tuple[int, List[str]]:
        score, confirmations = 0, []
        ichi_data = self.get_indicator('ichimoku', analysis_source=analysis_data)
        if not self._indicator_ok(ichi_data):
            return 0, []

        analysis = ichi_data.get('analysis', {})

        def check(name: str, weight_key: str, condition: bool):
            nonlocal score
            if condition:
                points = weights.get(weight_key, 0)
                score += points
                confirmations.append(name)
                self._log_criteria(f"IchiComponent: {name}", True, f"Condition met, adding {points} points.")

        # 1. Price vs Kumo
        if direction == "BUY":
            check("Price>Kumo", 'price_vs_kumo', analysis.get('price_position') == "Above Kumo")
        else: # SELL
            check("Price<Kumo", 'price_vs_kumo', analysis.get('price_position') == "Below Kumo")

        # 2. TK Cross Strength
        tk_cross = str(analysis.get('tk_cross', "")).lower()
        is_strong = "strong" in tk_cross
        is_aligned = ("bullish" in tk_cross and direction == "BUY") or \
                     ("bearish" in tk_cross and direction == "SELL")

        if is_aligned:
            if is_strong:
                check("Strong_TK_Cross", 'tk_cross_strong', True)
            else:
                check("Medium_TK_Cross", 'tk_cross_medium', True)
        
        # 3. Future Kumo Direction
        future_kumo = analysis.get('future_kumo_direction', "")
        check("Future_Kumo_Aligned", 'future_kumo', 
              (future_kumo == "Bullish" and direction == "BUY") or \
              (future_kumo == "Bearish" and direction == "SELL"))

        # 4. Chikou Span Status
        chikou_status = analysis.get('chikou_status', "")
        check("Chikou_Free", 'chikou_free', 
              ("Free (Bullish)" in chikou_status and direction == "BUY") or \
              ("Free (Bearish)" in chikou_status and direction == "SELL"))

        # 5. Kumo Twist
        kumo_twist = analysis.get('kumo_twist', "")
        check("Kumo_Twist_Aligned", 'kumo_twist',
              (kumo_twist == "Bullish Twist" and direction == "BUY") or \
              (kumo_twist == "Bearish Twist" and direction == "SELL"))

        # 6. Volume Spike (Z-Score) - Robust Access
        volume_data = self.get_indicator('volume', analysis_source=analysis_data) or {}
        vol_analysis = volume_data.get('analysis') or {}
        vol_values = volume_data.get('values') or {}
        volume_z_score = vol_analysis.get('zscore') if vol_analysis.get('zscore') is not None else vol_values.get('zscore')
        
        z_threshold = float(self.config.get('volume_z_threshold', 2.0))
        if volume_z_score is not None:
            check("Volume_Spike", 'volume_spike', volume_z_score >= z_threshold)
            
        return score, confirmations

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        if not self.price_data:
            self._log_final_decision("HOLD", "No price data available.")
            return None

        required_names = ['ichimoku', 'adx', 'atr', 'volume']
        indicators = {name: self.get_indicator(name) for name in required_names}
        
        # ✅ PATCH v6.1: Robust indicator validation
        if any(not self._indicator_ok(data) for data in indicators.values()):
            missing = [name for name, data in indicators.items() if not self._indicator_ok(data)]
            self._log_final_decision("HOLD", f"Missing or invalid indicator data for: {', '.join(missing)}")
            return None

        # --- 1. Determine Signal Direction (Expanded Trigger Logic) ---
        ichi_analysis = indicators['ichimoku']['analysis'] or {}
        ichi_values = indicators['ichimoku']['values'] or {}
        
        signal_direction: Optional[str] = None
        tk_cross = str(ichi_analysis.get('tk_cross', "")).lower()
        
        if "bullish" in tk_cross:
            signal_direction = "BUY"
        elif "bearish" in tk_cross:
            signal_direction = "SELL"
        else: # Alternative Trigger: Cloud Breakout Structure
            price_pos = ichi_analysis.get('price_position')
            senkou_a = ichi_values.get('senkou_a')
            senkou_b = ichi_values.get('senkou_b')
            if price_pos == "Above Kumo" and senkou_a is not None and senkou_b is not None and senkou_a > senkou_b:
                signal_direction = "BUY"
                self._log_criteria("Trigger Source", True, "Cloud Breakout Structure (Bullish)")
            elif price_pos == "Below Kumo" and senkou_a is not None and senkou_b is not None and senkou_a < senkou_b:
                signal_direction = "SELL"
                self._log_criteria("Trigger Source", True, "Cloud Breakout Structure (Bearish)")

        if signal_direction is None:
            self._log_final_decision("HOLD", "No primary trigger from TK Cross or Cloud Structure.")
            return None
        self._log_criteria("Primary Trigger", True, f"Signal direction '{signal_direction}' established.")
        
        # --- 2. Determine Market Regime & Dynamic Score Threshold ---
        adx_val = float((indicators['adx']['values'] or {}).get('adx', 0.0))
        mr_threshold = float(cfg.get('market_regime_adx', 21))
        market_regime = "TRENDING" if adx_val > mr_threshold else "RANGING"
        active_weights = cfg.get('weights_trending') if market_regime == "TRENDING" else cfg.get('weights_ranging')
        self._log_criteria("Market Regime", True, f"Regime='{market_regime}' (ADX={adx_val:.2f})")
        
        min_score_base = float(cfg.get('min_total_score_base', 62.0))
        if adx_val < 18:
            min_score = min_score_base - 4.0
        elif adx_val < mr_threshold:
            min_score = min_score_base - 2.0
        else:
            min_score = min_score_base
        self._log_criteria("Dynamic Min Score", True, f"Minimum score set to {min_score} based on ADX.")

        # --- 3. Calculate Scores (Primary & HTF) ---
        primary_score, primary_confirms = self._score_ichimoku(signal_direction, self.analysis, active_weights)
        
        htf_score, htf_confirms = 0, []
        htf_enabled = bool(cfg.get('htf_confirmation_enabled')) and bool(self.htf_analysis)
        
        if htf_enabled:
            htf_score, htf_confirms = self._score_ichimoku(signal_direction, self.htf_analysis, active_weights)

        # --- 4. Normalize and Combine Scores with Intelligent HTF Logic ---
        max_possible_score = sum(active_weights.values())
        norm_primary_score = round((primary_score / max_possible_score) * 100, 2) if max_possible_score > 0 else 0.0
        norm_htf_score = round((htf_score / max_possible_score) * 100, 2) if htf_enabled and max_possible_score > 0 else 0.0
        
        if norm_primary_score >= float(cfg.get('primary_override_threshold', 80.0)):
            htf_enabled = False
            self._log_criteria("HTF Logic", True, f"Primary score {norm_primary_score:.2f} is above override threshold. HTF ignored.")
            
        w_primary = float(cfg.get('score_weight_primary', 0.75))
        w_htf = float(cfg.get('score_weight_htf', 0.25))

        if htf_enabled:
            htf_ichi_analysis = (self.get_indicator('ichimoku', analysis_source=self.htf_analysis) or {}).get('analysis', {})
            htf_tk_cross = str(htf_ichi_analysis.get('tk_cross', "")).lower()
            htf_direction = "BUY" if "bullish" in htf_tk_cross else "SELL" if "bearish" in htf_tk_cross else None
            if htf_direction and htf_direction != signal_direction:
                self._log_criteria("HTF Logic", False, f"Conflict detected! PT is {signal_direction}, HTF is {htf_direction}. Dampening HTF weight.")
                w_htf = float(cfg.get('htf_conflict_dampen_weight', 0.15))
                w_primary = 1.0 - w_htf

        final_weighted_score = (norm_primary_score * w_primary) + (norm_htf_score * w_htf) if htf_enabled else norm_primary_score
        
        log_score_details = (f"Weighted Score={final_weighted_score:.2f} (Primary: {norm_primary_score:.0f}%*{w_primary*100}%, "
                             f"HTF: {norm_htf_score:.0f}%*{w_htf*100}%)" if htf_enabled else f"Score={final_weighted_score:.2f} (Primary only)")
        
        score_is_ok = final_weighted_score >= min_score
        self._log_criteria("Total Score Check", score_is_ok, f"{log_score_details} vs min={min_score}")
        if not score_is_ok:
            self._log_final_decision("HOLD", f"Final score {final_weighted_score:.2f} < minimum {min_score}.")
            return None

        # --- 5. Calculate Stop-Loss (Hybrid Logic) & R/R ---
        entry_price = self.price_data.get('close')
        if entry_price is None:
            self._log_final_decision("HOLD", "Could not determine entry price.")
            return None

        sl_mode = str(cfg.get('sl_mode', 'hybrid')).lower()
        atr_val = (indicators['atr']['values'] or {}).get('atr')
        stop_loss: Optional[float] = None

        if sl_mode == 'hybrid' and atr_val:
            kijun_sl = ichi_values.get('kijun')
            kumo_sl = ichi_values.get('senkou_b') if signal_direction == 'BUY' else ichi_values.get('senkou_a')
            structural_sl = kumo_sl if kumo_sl is not None else kijun_sl

            if structural_sl and abs(entry_price - structural_sl) > 2.5 * atr_val:
                if signal_direction == 'BUY':
                    stop_loss = max(kijun_sl or (entry_price - 2 * atr_val), entry_price - 2 * atr_val)
                else: # SELL
                    stop_loss = min(kijun_sl or (entry_price + 2 * atr_val), entry_price + 2 * atr_val)
                self._log_criteria("Stop Loss", True, f"Hybrid SL: Structural SL too far, using ATR-based SL: {stop_loss}")
            else:
                stop_loss = structural_sl
                self._log_criteria("Stop Loss", True, f"Hybrid SL: Using structural SL: {stop_loss}")
        else:
            stop_loss = ichi_values.get('senkou_b') if sl_mode == 'kumo' else ichi_values.get('kijun')

        if stop_loss is None:
            self._log_final_decision("HOLD", "Could not set Stop Loss (value is None).")
            return None

        rr_needed = 2.0 if norm_primary_score >= 80.0 else float(cfg.get('min_rr_ratio', 1.8))
        
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        rr_val = (risk_params or {}).get("risk_reward_ratio")
        rr_is_ok = rr_val is not None and rr_val >= rr_needed
        rr_display = f"{rr_val:.2f}" if rr_val is not None else "N/A"
        
        self._log_criteria("Risk/Reward Check", rr_is_ok, f"R/R={rr_display} vs min required={rr_needed} (stepped)")
        if not rr_is_ok:
            self._log_final_decision("HOLD", "Risk/Reward ratio is too low or not calculable.")
            return None

        # --- 6. Final Confirmation ---
        confirmations = {
            "total_score": round(final_weighted_score, 2),
            "market_regime": market_regime,
            "primary_score_details": f"{primary_score}/{max_possible_score} ({','.join(primary_confirms)})",
            "htf_score_details": f"{htf_score}/{max_possible_score} ({','.join(htf_confirms)})" if htf_enabled else "N/A (Overridden or Disabled)",
            "rr_check": f"Passed (R/R={rr_display}, Needed={rr_needed})"
        }
        
        self._log_final_decision(signal_direction, "All criteria met. Ichimoku Hybrid Pro signal confirmed.")
        return {
            "direction": signal_direction,
            "entry_price": entry_price,
            **risk_params,
            "confirmations": confirmations
        }
