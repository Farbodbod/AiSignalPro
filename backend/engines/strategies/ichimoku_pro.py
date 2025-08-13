import logging
from typing import Dict, Any, Optional, List
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class IchimokuHybridPro(BaseStrategy):
    """
    IchimokuHybridPro - (v4.0 - Grandmaster Edition)
    -------------------------------------------------------------------------
    This world-class version is a true Ichimoku grandmaster. It operates on a
    multi-dimensional, adaptive scoring engine, featuring:
    1.  Deep MTF Confluence: Scores both primary and HTF Ichimoku signals.
    2.  Volume Power Filter: Integrates whale activity into its scoring logic.
    3.  Adaptive Weights: Uses different scoring models for RANGING vs TRENDING markets.
    """
    strategy_name: str = "IchimokuHybridPro"

    # ✅ MIRACLE UPGRADE: Default configuration for the Grandmaster engine
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
        "htf_confirmations": {} # We use our own deep MTF analysis now
    }

    def _score_ichimoku(self, direction: str, analysis_data: Dict, weights: Dict) -> tuple[int, List[str]]:
        """The core scoring engine for a single timeframe's analysis data."""
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
            
        # Volume Confirmation
        whales_data = self.get_indicator('whales', analysis_source=analysis_data)
        if whales_data and whales_data['analysis'].get('is_whale_activity'):
            score += weights.get('volume_spike', 1)
            confirmations.append("Volume_Spike")
            
        return score, confirmations

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        if not self.price_data: return None
        
        # --- 1. Data Gathering & Market Regime Detection ---
        ichimoku_data = self.get_indicator('ichimoku')
        adx_data = self.get_indicator('adx')
        if not all([ichimoku_data, adx_data]): return None

        market_regime = "TRENDING" if adx_data['values'].get('adx', 0) > cfg.get('market_regime_adx', 23) else "RANGING"
        active_weights = cfg.get('weights_trending') if market_regime == "TRENDING" else cfg.get('weights_ranging')

        # --- 2. Primary Trigger & Multi-Dimensional Scoring ---
        tk_cross = ichimoku_data.get('analysis', {}).get('tk_cross')
        signal_direction = "BUY" if "Bullish" in tk_cross else "SELL" if "Bearish" in tk_cross else None
        if not signal_direction: return None

        primary_score, primary_confirms = self._score_ichimoku(signal_direction, self.analysis, active_weights)
        htf_score, htf_confirms = (0, [])
        if cfg.get('htf_confirmation_enabled'):
            htf_score, htf_confirms = self._score_ichimoku(signal_direction, self.htf_analysis, active_weights)
        
        total_score = primary_score + htf_score
        
        if total_score < cfg.get('min_total_score', 10): return None
        
        logger.info(f"[{self.strategy_name}] Grandmaster Signal: {signal_direction} with Total Score {total_score} in {market_regime} market.")
        confirmations = {
            "total_score": total_score,
            "market_regime": market_regime,
            "primary_score": f"{primary_score} ({','.join(primary_confirms)})",
            "htf_score": f"{htf_score} ({','.join(htf_confirms)})"
        }
        
        # --- 3. Ichimoku-Native Risk Management ---
        entry_price = self.price_data.get('close')
        if not entry_price: return None

        ichi_values = ichimoku_data.get('values', {})
        stop_loss = None
        if cfg.get('sl_mode') == 'kijun': stop_loss = ichi_values.get('kijun')
        elif cfg.get('sl_mode') == 'kumo':
            stop_loss = ichi_values.get('senkou_b')
        if not stop_loss: return None
            
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        
        if not risk_params or risk_params.get("risk_reward_ratio", 0) < cfg.get('min_rr_ratio', 1.5):
            return None
        confirmations['rr_check'] = f"Passed (R/R: {risk_params.get('risk_reward_ratio')})"

        logger.info(f"✨✨ [{self.strategy_name}] ICHIMOKU GRANDMASTER SIGNAL CONFIRMED! ✨✨")

        # --- 4. Package and Return ---
        return { "direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations }
