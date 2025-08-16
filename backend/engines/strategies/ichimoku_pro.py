# strategies/ichimoku_hybrid_pro.py (v4.2 - High-Clarity Score Logging)

import logging
from typing import Dict, Any, Optional, List
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class IchimokuHybridPro(BaseStrategy):
    """
    IchimokuHybridPro - (v4.2 - High-Clarity Score Logging)
    -------------------------------------------------------------------------
    This version enhances the logging for the score check to provide a clear
    breakdown of the primary score vs. the HTF confirmation score, offering
    ultimate transparency into the final decision.
    """
    strategy_name: str = "IchimokuHybridPro"

    default_config = {
        # ... (بخش کانفیگ بدون تغییر است) ...
        "min_total_score": 10,
        "market_regime_adx": 23,
        "sl_mode": "kumo",
        "min_rr_ratio": 2.0,
        "weights_trending": { "price_vs_kumo": 2, "tk_cross_strong": 3, "future_kumo": 2, "chikou_free": 2, "kumo_twist": 1, "volume_spike": 1 },
        "weights_ranging": { "price_vs_kumo": 1, "tk_cross_strong": 2, "future_kumo": 1, "chikou_free": 1, "kumo_twist": 3, "volume_spike": 2 },
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {}
    }

    def _score_ichimoku(self, direction: str, analysis_data: Dict, weights: Dict) -> tuple[int, List[str]]:
        # ... (این تابع بدون تغییر است) ...
        score, confirmations = 0, []
        if not analysis_data: return 0, []
        ichi_data = self.get_indicator('ichimoku', analysis_source=analysis_data)
        if not ichi_data: return 0, []
        analysis = ichi_data.get('analysis', {})
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
        if whales_data and whales_data.get('analysis',{}).get('is_whale_activity'):
            score += weights.get('volume_spike', 1); confirmations.append("Volume_Spike")
        return score, confirmations

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        if not self.price_data:
            self._log_final_decision("HOLD", "No price data available.")
            return None
        
        ichimoku_data = self.get_indicator('ichimoku')
        adx_data = self.get_indicator('adx')
        
        self._log_criteria("Ichimoku Data Check", ichimoku_data is not None, "Ichimoku data is missing.")
        self._log_criteria("ADX Data Check", adx_data is not None, "ADX data is missing.")
        
        if not all([ichimoku_data, adx_data]):
            self._log_final_decision("HOLD", "Required indicator data is missing.")
            return None
        
        market_regime = "TRENDING" if adx_data.get('values', {}).get('adx', 0) > cfg.get('market_regime_adx', 23) else "RANGING"
        active_weights = cfg.get('weights_trending') if market_regime == "TRENDING" else cfg.get('weights_ranging')
        self._log_criteria("Market Regime Detection", True, f"Market regime detected as '{market_regime}' (ADX: {adx_data.get('values', {}).get('adx', 0):.2f})")
        
        tk_cross = ichimoku_data.get('analysis', {}).get('tk_cross')
        signal_direction = "BUY" if "Bullish" in tk_cross else "SELL" if "Bearish" in tk_cross else None
        self._log_criteria("TK Cross Trigger", signal_direction is not None, f"TK Cross signal is '{tk_cross}'")
        if not signal_direction:
            self._log_final_decision("HOLD", "No primary trigger signal from Ichimoku.")
            return None

        primary_score, primary_confirms = self._score_ichimoku(signal_direction, self.analysis, active_weights)
        htf_score, htf_confirms = (0, [])
        if cfg.get('htf_confirmation_enabled') and self.htf_analysis:
            htf_score, htf_confirms = self._score_ichimoku(signal_direction, self.htf_analysis, active_weights)
        
        total_score = primary_score + htf_score
        min_score = cfg.get('min_total_score', 10)
        
        # ✅ IMPROVED LOGGING: The reason now includes the score breakdown.
        score_reason = f"Total score {total_score} (Primary: {primary_score} + HTF: {htf_score}) is below minimum of {min_score}."
        self._log_criteria("Total Score Check", total_score >= min_score, score_reason)
        if total_score < min_score:
            self._log_final_decision("HOLD", f"Total score ({total_score}) is below minimum threshold.")
            return None
        
        # ... (بقیه کد برای مدیریت ریسک و صدور سیگنال بدون تغییر است) ...
        confirmations = { "total_score": total_score, "market_regime": market_regime, "primary_score": f"{primary_score} ({','.join(primary_confirms)})", "htf_score": f"{htf_score} ({','.join(htf_confirms)})" }
        entry_price = self.price_data.get('close')
        if not entry_price:
            self._log_final_decision("HOLD", "Could not determine entry price."); return None

        ichi_values, stop_loss = ichimoku_data.get('values', {}), None
        if cfg.get('sl_mode') == 'kijun':
            stop_loss = ichi_values.get('kijun')
            self._log_criteria("Stop Loss Source", stop_loss is not None, f"Kijun line used: {stop_loss}")
        elif cfg.get('sl_mode') == 'kumo':
            stop_loss = ichi_values.get('senkou_b')
            self._log_criteria("Stop Loss Source", stop_loss is not None, f"Senkou B line used: {stop_loss}")
        if not stop_loss:
            self._log_final_decision("HOLD", "Could not set Stop Loss."); return None
            
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        rr_is_ok = risk_params and risk_params.get("risk_reward_ratio", 0) >= cfg.get('min_rr_ratio', 1.5)
        self._log_criteria("Risk/Reward Check", rr_is_ok, f"R/R check failed. (Calculated: {risk_params.get('risk_reward_ratio')})")
        if not rr_is_ok:
            self._log_final_decision("HOLD", "Risk/Reward ratio is too low."); return None
        
        confirmations['rr_check'] = f"Passed (R/R: {risk_params.get('risk_reward_ratio')})"
        self._log_final_decision(signal_direction, "All criteria met. Ichimoku Hybrid signal confirmed.")
        
        return { "direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations }

