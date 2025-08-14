# strategies/ichimoku_hybrid_pro.py (v4.1 - Enhanced Logging Edition)

import logging
from typing import Dict, Any, Optional, List
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class IchimokuHybridPro(BaseStrategy):
    """
    IchimokuHybridPro - (v4.1 - Enhanced Logging Edition)
    -------------------------------------------------------------------------
    This version integrates the new logging mechanism for transparent decision-making.
    """
    strategy_name: str = "IchimokuHybridPro"

    default_config = {
        "min_total_score": 10,
        "market_regime_adx": 23,
        "sl_mode": "kumo",
        "min_rr_ratio": 2.0,
        "weights_trending": {
            "price_vs_kumo": 2, "tk_cross_strong": 3, "future_kumo": 2,
            "chikou_free": 2, "kumo_twist": 1, "volume_spike": 1
        },
        "weights_ranging": {
            "price_vs_kumo": 1, "tk_cross_strong": 2, "future_kumo": 1,
            "chikou_free": 1, "kumo_twist": 3, "volume_spike": 2
        },
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {}
    }

    def _score_ichimoku(self, direction: str, analysis_data: Dict, weights: Dict) -> tuple[int, List[str]]:
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
        if whales_data and whales_data['analysis'].get('is_whale_activity'):
            score += weights.get('volume_spike', 1)
            confirmations.append("Volume_Spike")
            
        return score, confirmations

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        if not self.price_data:
            self._log_final_decision("HOLD", "No price data available.")
            return None
        
        # --- 1. Data Gathering & Market Regime Detection ---
        ichimoku_data = self.get_indicator('ichimoku')
        adx_data = self.get_indicator('adx')
        
        # Log data availability checks
        self._log_criteria("Ichimoku Data Check", ichimoku_data is not None, "Ichimoku data is missing." if ichimoku_data is None else "Ichimoku data is present.")
        self._log_criteria("ADX Data Check", adx_data is not None, "ADX data is missing." if adx_data is None else "ADX data is present.")
        
        if not all([ichimoku_data, adx_data]):
            self._log_final_decision("HOLD", "Required indicator data is missing.")
            return None
        
        market_regime = "TRENDING" if adx_data['values'].get('adx', 0) > cfg.get('market_regime_adx', 23) else "RANGING"
        active_weights = cfg.get('weights_trending') if market_regime == "TRENDING" else cfg.get('weights_ranging')
        
        self._log_criteria("Market Regime Detection", True, f"Market regime detected as '{market_regime}' (ADX: {adx_data['values'].get('adx', 0):.2f})")
        
        # --- 2. Primary Trigger & Multi-Dimensional Scoring ---
        tk_cross = ichimoku_data.get('analysis', {}).get('tk_cross')
        signal_direction = "BUY" if "Bullish" in tk_cross else "SELL" if "Bearish" in tk_cross else None
        
        self._log_criteria("TK Cross Trigger", signal_direction is not None, "No strong TK cross signal detected." if signal_direction is None else f"TK Cross signal is '{signal_direction}'")

        if not signal_direction:
            self._log_final_decision("HOLD", "No primary trigger signal from Ichimoku.")
            return None

        primary_score, primary_confirms = self._score_ichimoku(signal_direction, self.analysis, active_weights)
        htf_score, htf_confirms = (0, [])
        if cfg.get('htf_confirmation_enabled'):
            htf_score, htf_confirms = self._score_ichimoku(signal_direction, self.htf_analysis, active_weights)
        
        total_score = primary_score + htf_score
        
        self._log_criteria("Total Score Check", total_score >= cfg.get('min_total_score', 10), f"Total score of {total_score} is below minimum {cfg.get('min_total_score', 10)}.")
        
        if total_score < cfg.get('min_total_score', 10):
            self._log_final_decision("HOLD", f"Total score ({total_score}) is below minimum threshold.")
            return None
        
        confirmations = {
            "total_score": total_score,
            "market_regime": market_regime,
            "primary_score": f"{primary_score} ({','.join(primary_confirms)})",
            "htf_score": f"{htf_score} ({','.join(htf_confirms)})"
        }
        
        # --- 3. Ichimoku-Native Risk Management ---
        entry_price = self.price_data.get('close')
        if not entry_price:
            self._log_final_decision("HOLD", "Could not determine entry price.")
            return None

        ichi_values = ichimoku_data.get('values', {})
        stop_loss = None
        
        if cfg.get('sl_mode') == 'kijun':
            stop_loss = ichi_values.get('kijun')
            self._log_criteria("Stop Loss Source", stop_loss is not None, "Kijun line not available." if stop_loss is None else f"Kijun line used as Stop Loss: {stop_loss}")
        elif cfg.get('sl_mode') == 'kumo':
            stop_loss = ichi_values.get('senkou_b')
            self._log_criteria("Stop Loss Source", stop_loss is not None, "Senkou B line not available." if stop_loss is None else f"Senkou B line used as Stop Loss: {stop_loss}")
            
        if not stop_loss:
            self._log_final_decision("HOLD", "Could not set Stop Loss based on selected mode.")
            return None
            
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)

        # Log Risk/Reward check
        rr_is_ok = risk_params and risk_params.get("risk_reward_ratio", 0) >= cfg.get('min_rr_ratio', 1.5)
        self._log_criteria("Risk/Reward Check", rr_is_ok, "Failed R/R check." if not rr_is_ok else f"Passed with R/R: {risk_params.get('risk_reward_ratio')}")
        
        if not rr_is_ok:
            self._log_final_decision("HOLD", "Risk/Reward ratio is too low.")
            return None
        
        confirmations['rr_check'] = f"Passed (R/R: {risk_params.get('risk_reward_ratio')})"

        # --- 4. Final Decision & Return ---
        final_summary = { "direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations }
        self._log_final_decision(signal_direction, "All criteria met. Grandmaster signal confirmed.")
        
        return final_summary
