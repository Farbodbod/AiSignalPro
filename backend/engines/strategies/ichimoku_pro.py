# backend/engines/strategies/ichimoku_hybrid_pro.py (v5.2 - The Syntax Hotfix)

from __future__ import annotations
import logging
from typing import Dict, Any, Optional, List, Tuple, ClassVar
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class IchimokuHybridPro(BaseStrategy):
    """
    IchimokuHybridPro - (v5.2 - The Syntax Hotfix)
    -------------------------------------------------------------------------
    This version contains a critical hotfix for a SyntaxError in the data
    availability check (items' -> items()). All other powerful features and
    logic from v5.1, including the Score Integrity fix, are fully preserved.
    This version is now stable and production-ready.
    """
    strategy_name: str = "IchimokuHybridPro"
    default_config: ClassVar[Dict[str, Any]] = {
        "min_total_score": 65.0,
        "market_regime_adx": 23,
        "sl_mode": "kumo",
        "min_rr_ratio": 2.0,
        "weights_trending": { "price_vs_kumo": 2, "tk_cross_strong": 3, "future_kumo": 2, "chikou_free": 2, "kumo_twist": 1, "volume_spike": 1 },
        "weights_ranging": { "price_vs_kumo": 1, "tk_cross_strong": 2, "future_kumo": 1, "chikou_free": 1, "kumo_twist": 3, "volume_spike": 2 },
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {}
    }

    def _score_ichimoku(self, direction: str, analysis_data: Dict, weights: Dict) -> Tuple[int, List[str]]:
        score, confirmations = 0, []
        ichi_data = self.get_indicator('ichimoku', analysis_source=analysis_data)
        if not ichi_data or not ichi_data.get('analysis'): return 0, []
        
        analysis = ichi_data['analysis']
        
        def check(name: str, weight_key: str, condition: bool):
            nonlocal score
            if condition:
                points = weights.get(weight_key, 0)
                score += points
                confirmations.append(name)
                self._log_criteria(f"IchiComponent: {name}", True, f"Condition met, adding {points} points.")
        
        if direction == "BUY":
            check("Price>Kumo", 'price_vs_kumo', analysis.get('price_position') == "Above Kumo")
            check("Strong_TK_Cross", 'tk_cross_strong', analysis.get('tk_cross') == "Strong Bullish")
            check("Future_Kumo_Bullish", 'future_kumo', analysis.get('future_kumo_direction') == "Bullish")
            check("Chikou_Free", 'chikou_free', analysis.get('chikou_status') == "Free (Bullish)")
            check("Kumo_Twist", 'kumo_twist', analysis.get('kumo_twist') == "Bullish Twist")
        elif direction == "SELL":
            check("Price<Kumo", 'price_vs_kumo', analysis.get('price_position') == "Below Kumo")
            check("Strong_TK_Cross", 'tk_cross_strong', analysis.get('tk_cross') == "Strong Bearish")
            check("Future_Kumo_Bearish", 'future_kumo', analysis.get('future_kumo_direction') == "Bearish")
            check("Chikou_Free", 'chikou_free', analysis.get('chikou_status') == "Free (Bearish)")
            check("Kumo_Twist", 'kumo_twist', analysis.get('kumo_twist') == "Bearish Twist")
        
        whales_data = self.get_indicator('whales', analysis_source=analysis_data)
        if whales_data and (whales_data.get('analysis') or {}).get('is_whale_activity'):
            check("Volume_Spike", 'volume_spike', True)
        
        return score, confirmations

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        if not self.price_data: self._log_final_decision("HOLD", "No price data available."); return None

        required_names = ['ichimoku', 'adx', 'whales']
        indicators = {name: self.get_indicator(name) for name in required_names}
        
        # ✅ SYNTAX HOTFIX (v5.2): Corrected items' to items()
        missing = [name for name, data in indicators.items() if data is None or not data.get('values')]
        
        if missing:
            reason = f"Invalid/Missing indicators (or 'values' key): {', '.join(missing)}"
            self._log_criteria("Data Availability", False, reason); self._log_final_decision("HOLD", reason); return None
        self._log_criteria("Data Availability", True, "All required indicators are present.")

        adx_val = float((indicators['adx']['values'] or {}).get('adx', 0.0))
        mr_threshold = float(cfg.get('market_regime_adx', 23))
        market_regime = "TRENDING" if adx_val > mr_threshold else "RANGING"
        active_weights = cfg.get('weights_trending') if market_regime == "TRENDING" else cfg.get('weights_ranging')
        self._log_criteria("Market Regime Detection", True, f"Market regime='{market_regime}' (ADX={adx_val:.2f})")
        
        tk_cross = (indicators['ichimoku']['analysis'] or {}).get('tk_cross')
        tk_str = str(tk_cross or "").lower()
        signal_direction: Optional[str] = "BUY" if "bullish" in tk_str else "SELL" if "bearish" in tk_str else None
        self._log_criteria("TK Cross Trigger", signal_direction is not None, f"TK Cross='{tk_str.title()}'")
        if signal_direction is None: self._log_final_decision("HOLD", "No primary trigger from Ichimoku."); return None

        primary_score, primary_confirms = self._score_ichimoku(signal_direction, self.analysis, active_weights)
        
        htf_score, htf_confirms = 0, []
        htf_enabled_flag = bool(cfg.get('htf_confirmation_enabled'))
        htf_available = htf_enabled_flag and bool(self.htf_analysis)
        
        if htf_available:
            htf_score, htf_confirms = self._score_ichimoku(signal_direction, self.htf_analysis, active_weights)
        
        raw_total_score = primary_score + htf_score
        htf_multiplier = 2 if htf_available else 1
        max_possible_score = sum(active_weights.values()) * htf_multiplier
        
        normalized_score = round((raw_total_score / max_possible_score) * 100, 2) if max_possible_score > 0 else 0.0

        min_score = float(cfg.get('min_total_score', 75.0))
        score_is_ok = normalized_score >= min_score
        self._log_criteria("Total Score Check", score_is_ok, f"Score={normalized_score:.2f} vs min={min_score} (Raw: {raw_total_score}/{max_possible_score})")
        if not score_is_ok: self._log_final_decision("HOLD", f"Total score {normalized_score:.2f} < minimum {min_score}."); return None

        entry_price = self.price_data.get('close')
        if entry_price is None: self._log_final_decision("HOLD", "Could not determine entry price."); return None

        sl_mode = str(cfg.get('sl_mode', 'kumo')).lower()
        stop_loss: Optional[float] = None
        if sl_mode == 'kijun': stop_loss = (indicators['ichimoku']['values'] or {}).get('kijun')
        elif sl_mode == 'kumo': stop_loss = (indicators['ichimoku']['values'] or {}).get('senkou_b')
        self._log_criteria("Stop Loss Source", stop_loss is not None, f"SL mode={sl_mode}, Value={stop_loss}")
        if stop_loss is None: self._log_final_decision("HOLD", "Could not set Stop Loss (value is None)."); return None
            
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        rr_needed = float(cfg.get('min_rr_ratio', 2.0))
        rr_val = (risk_params or {}).get("risk_reward_ratio")
        rr_display = f"{rr_val:.2f}" if rr_val is not None else "N/A"
        rr_is_ok = rr_val is not None and rr_val >= rr_needed
        self._log_criteria("Risk/Reward Check", rr_is_ok, f"R/R={rr_display} vs min required={rr_needed}")
        if not rr_is_ok: self._log_final_decision("HOLD", "Risk/Reward ratio is too low or not calculable."); return None
        
        confirmations = {
            "total_score": normalized_score, "market_regime": market_regime,
            "primary_score_details": f"{primary_score} ({','.join(primary_confirms)})",
            "htf_score_details": f"{htf_score} ({','.join(htf_confirms)})",
            "rr_check": f"Passed (R/R={rr_display})"
        }
        self._log_final_decision(signal_direction, "All criteria met. Ichimoku Hybrid signal confirmed.")
        
        return { "direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations }
