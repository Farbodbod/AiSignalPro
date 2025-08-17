# strategies/ichimoku_hybrid_pro.py (v4.4 – Hardened & Peer-Reviewed)

from __future__ import annotations
import logging
from typing import Dict, Any, Optional, List, Tuple, ClassVar
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class IchimokuHybridPro(BaseStrategy):
    """
    IchimokuHybridPro - (v4.4 – Hardened & Peer-Reviewed)
    -------------------------------------------------------------------------
    This version incorporates a full peer review, fixing critical edge cases:
    - Fix: Safe handling of None values for tk_cross to prevent TypeError.
    - Fix: Use of `is None` for price/SL checks to correctly handle `0.0` values.
    - Fix: Safe logging for R/R values to prevent AttributeError.
    - Robustness: Added fallback for unknown sl_mode and enhanced log messages with values.
    - Quality: Implemented ClassVar and richer type hints.
    """
    strategy_name: str = "IchimokuHybridPro"
    default_config: ClassVar[Dict[str, Any]] = {
        "min_total_score": 12,
        "market_regime_adx": 23,
        "sl_mode": "kumo", # options: 'kijun' | 'kumo'
        "min_rr_ratio": 2.0,
        "weights_trending": { "price_vs_kumo": 2, "tk_cross_strong": 3, "future_kumo": 2, "chikou_free": 2, "kumo_twist": 1, "volume_spike": 1 },
        "weights_ranging": { "price_vs_kumo": 1, "tk_cross_strong": 2, "future_kumo": 1, "chikou_free": 1, "kumo_twist": 3, "volume_spike": 2 },
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {}
    }

    def _score_ichimoku(self, direction: str, analysis_data: Optional[Dict], weights: Dict) -> Tuple[int, List[str]]:
        score, confirmations = 0, []
        if not analysis_data: return 0, []
        ichi_data = self.get_indicator('ichimoku', analysis_source=analysis_data)
        if not ichi_data: return 0, []
        
        analysis = ichi_data.get('analysis') or {}
        
        if direction == "BUY":
            if analysis.get('price_position') == "Above Kumo": score += weights.get('price_vs_kumo', 2); confirmations.append("Price>Kumo")
            if analysis.get('tk_cross') == "Strong Bullish": score += weights.get('tk_cross_strong', 3); confirmations.append("Strong_TK_Cross")
            if analysis.get('future_kumo_direction') == "Bullish": score += weights.get('future_kumo', 2); confirmations.append("Future_Kumo_Bullish")
            if analysis.get('chikou_status') == "Free (Bullish)": score += weights.get('chikou_free', 2); confirmations.append("Chikou_Free")
            if analysis.get('kumo_twist') == "Bullish Twist": score += weights.get('kumo_twist', 1); confirmations.append("Kumo_Twist")
        elif direction == "SELL":
            if analysis.get('price_position') == "Below Kumo": score += weights.get('price_vs_kumo', 2); confirmations.append("Price<Kumo")
            if analysis.get('tk_cross') == "Strong Bearish": score += weights.get('tk_cross_strong', 3); confirmations.append("Strong_TK_Cross")
            if analysis.get('future_kumo_direction') == "Bearish": score += weights.get('future_kumo', 2); confirmations.append("Future_Kumo_Bearish")
            if analysis.get('chikou_status') == "Free (Bearish)": score += weights.get('chikou_free', 2); confirmations.append("Chikou_Free")
            if analysis.get('kumo_twist') == "Bearish Twist": score += weights.get('kumo_twist', 1); confirmations.append("Kumo_Twist")
        
        whales_data = self.get_indicator('whales', analysis_source=analysis_data)
        if whales_data and (whales_data.get('analysis') or {}).get('is_whale_activity'):
            score += weights.get('volume_spike', 1); confirmations.append("Volume_Spike")
        
        return score, confirmations

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        if not self.price_data:
            self._log_final_decision("HOLD", "No price data available.")
            return None

        ichimoku_data = self.get_indicator('ichimoku')
        adx_data = self.get_indicator('adx')

        self._log_criteria("Ichimoku Data Check", ichimoku_data is not None, "Ichimoku data is missing." if ichimoku_data is None else "Ichimoku data is present.")
        self._log_criteria("ADX Data Check", adx_data is not None, "ADX data is missing." if adx_data is None else "ADX data is present.")
        if not ichimoku_data or not adx_data:
            self._log_final_decision("HOLD", "Required indicator data is missing.")
            return None

        # --- Market Regime ---
        adx_val = float((adx_data.get('values') or {}).get('adx', 0.0))
        mr_threshold = float(cfg.get('market_regime_adx', 23))
        market_regime = "TRENDING" if adx_val > mr_threshold else "RANGING"
        active_weights = cfg.get('weights_trending') if market_regime == "TRENDING" else cfg.get('weights_ranging')
        self._log_criteria("Market Regime Detection", True, f"Market regime='{market_regime}' (ADX={adx_val:.2f})")
        
        # --- Primary Trigger: TK Cross ---
        tk_cross = (ichimoku_data.get('analysis') or {}).get('tk_cross')
        tk_str = str(tk_cross or "").lower() # ✅ FIX: Safe handling of None
        
        signal_direction: Optional[str] = None
        if "bullish" in tk_str: signal_direction = "BUY"
        elif "bearish" in tk_str: signal_direction = "SELL"

        self._log_criteria("TK Cross Trigger", signal_direction is not None, f"TK Cross='{tk_str.title()}'")
        if signal_direction is None:
            self._log_final_decision("HOLD", "No primary trigger signal from Ichimoku.")
            return None

        # --- Scoring (LTF + HTF) ---
        primary_score, primary_confirms = self._score_ichimoku(signal_direction, self.analysis, active_weights)
        htf_score, htf_confirms = 0, []
        if cfg.get('htf_confirmation_enabled') and getattr(self, "htf_analysis", None):
            htf_score, htf_confirms = self._score_ichimoku(signal_direction, self.htf_analysis, active_weights)
        
        total_score = primary_score + htf_score
        min_score = int(cfg.get('min_total_score', 10))
        self._log_criteria("Total Score Check", total_score >= min_score, f"Total={total_score} (Primary={primary_score}, HTF={htf_score}) vs min={min_score}")
        if total_score < min_score:
            self._log_final_decision("HOLD", f"Total score {total_score} < minimum {min_score}.")
            return None

        # --- Entry Price ---
        entry_price = self.price_data.get('close')
        if entry_price is None: # ✅ FIX: Use 'is None' check for price
            self._log_final_decision("HOLD", "Could not determine entry price.")
            return None

        # --- Stop Loss selection ---
        ichi_values = ichimoku_data.get('values') or {}
        sl_mode = str(cfg.get('sl_mode', 'kumo')).lower()
        stop_loss: Optional[float] = None
        if sl_mode == 'kijun':
            stop_loss = ichi_values.get('kijun')
            self._log_criteria("Stop Loss Source", stop_loss is not None, f"SL mode=kijun, Kijun Line={stop_loss}")
        elif sl_mode == 'kumo':
            stop_loss = ichi_values.get('senkou_b')
            self._log_criteria("Stop Loss Source", stop_loss is not None, f"SL mode=kumo, Senkou B={stop_loss}")
        else:
            self._log_criteria("Stop Loss Source", False, f"Unknown sl_mode='{sl_mode}'. Supported: 'kijun'|'kumo'")
        
        if stop_loss is None: # ✅ FIX: Use 'is None' check for SL
            self._log_final_decision("HOLD", "Could not set Stop Loss (value is None).")
            return None
            
        # --- Risk Management / R:R ---
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        rr_needed = float(cfg.get('min_rr_ratio', 2.0))
        rr_val = (risk_params or {}).get("risk_reward_ratio") # ✅ FIX: Safe access to R/R value for logging
        rr_is_ok = rr_val is not None and rr_val >= rr_needed
        
        self._log_criteria("Risk/Reward Check", rr_is_ok, f"R/R={rr_val} vs min required={rr_needed}")
        if not rr_is_ok:
            self._log_final_decision("HOLD", "Risk/Reward ratio is too low or could not be calculated.")
            return None
        
        confirmations: Dict[str, Any] = {
            "total_score": total_score,
            "market_regime": market_regime,
            "primary_score": f"{primary_score} ({','.join(primary_confirms)})",
            "htf_score": f"{htf_score} ({','.join(htf_confirms)})",
            "rr_check": f"Passed (R/R={rr_val})"
        }
        self._log_final_decision(signal_direction, "All criteria met. Ichimoku Hybrid signal confirmed.")
        
        return { "direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations }
