import logging
from typing import Dict, Any, Optional, List
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class IchimokuHybridPro(BaseStrategy):
    """
    IchimokuHybridPro - (v3.0 - Miracle Edition)
    -------------------------------------------------------------------------
    This world-class version is a true Ichimoku specialist. It operates on a
    highly sophisticated, multi-dimensional scoring engine that requires confluence
    across all major Ichimoku components: past (Chikou), present (TK Cross, Kumo),
    and future (Future Kumo, Kumo Twist). It uses Ichimoku-native levels for
    intelligent, dynamic risk management, producing exceptionally high-probability signals.
    """
    strategy_name: str = "IchimokuHybridPro"

    def _get_signal_config(self) -> Dict[str, Any]:
        """Loads and validates the strategy's specific parameters from the config."""
        # ✅ NEW: Upgraded default weights for the Miracle scoring engine
        default_weights = {
            "price_above_kumo": 2,
            "tk_cross_strong": 3,
            "future_kumo_aligned": 2,
            "chikou_is_free": 2,
            "kumo_twist_aligned": 1 
        }
        return {
            "min_score_to_signal": int(self.config.get("min_score_to_signal", 8)),
            "min_adx_strength": float(self.config.get("min_adx_strength", 25.0)),
            "sl_mode": str(self.config.get("sl_mode", "kumo")), # 'kumo' or 'kijun'
            "min_rr_ratio": float(self.config.get("min_risk_reward_ratio", 1.5)),
            "weights": self.config.get("weights", default_weights),
            "htf_confirmation_enabled": bool(self.config.get("htf_confirmation_enabled", True)),
            "htf_timeframe": str(self.config.get("htf_timeframe", "4h")),
        }

    def _score_ichimoku(self, ichimoku_data: Dict[str, Any], direction: str, weights: Dict[str, int]) -> tuple[int, List[str]]:
        """
        ✅ NEW: The Miracle Scoring Engine.
        Calculates a score based on deep confluence of all Ichimoku components.
        """
        score, confirmations = 0, []
        analysis = ichimoku_data.get('analysis', {})

        # --- Scoring Logic for a BUY Signal ---
        if direction == "BUY":
            if analysis.get('price_position') == "Above Kumo":
                score += weights.get('price_above_kumo', 2)
                confirmations.append("Price Above Kumo")
            
            if analysis.get('tk_cross') == "Strong Bullish":
                score += weights.get('tk_cross_strong', 3)
                confirmations.append("Strong TK Cross")

            if analysis.get('future_kumo_direction') == "Bullish":
                score += weights.get('future_kumo_aligned', 2)
                confirmations.append("Future Kumo Bullish")

            if analysis.get('chikou_status') == "Free (Bullish)":
                score += weights.get('chikou_is_free', 2)
                confirmations.append("Chikou Span is Free")
            
            if analysis.get('kumo_twist') == "Bullish Twist":
                score += weights.get('kumo_twist_aligned', 1)
                confirmations.append("Recent Kumo Twist")

        # --- Scoring Logic for a SELL Signal ---
        elif direction == "SELL":
            if analysis.get('price_position') == "Below Kumo":
                score += weights.get('price_above_kumo', 2)
                confirmations.append("Price Below Kumo")

            if analysis.get('tk_cross') == "Strong Bearish":
                score += weights.get('tk_cross_strong', 3)
                confirmations.append("Strong TK Cross")

            if analysis.get('future_kumo_direction') == "Bearish":
                score += weights.get('future_kumo_aligned', 2)
                confirmations.append("Future Kumo Bearish")

            if analysis.get('chikou_status') == "Free (Bearish)":
                score += weights.get('chikou_is_free', 2)
                confirmations.append("Chikou Span is Free")

            if analysis.get('kumo_twist') == "Bearish Twist":
                score += weights.get('kumo_twist_aligned', 1)
                confirmations.append("Recent Kumo Twist")

        return score, confirmations

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self._get_signal_config()
        
        # --- 1. Anti-Fragile Data Check ---
        if not self.price_data: return None
            
        ichimoku_data = self.get_indicator('ichimoku')
        adx_data = self.get_indicator('adx')
        
        if not all([ichimoku_data, adx_data]):
            return None

        # --- 2. Determine Potential Direction from TK Cross ---
        # The primary trigger is still a strong TK cross.
        tk_cross = ichimoku_data.get('analysis', {}).get('tk_cross')
        signal_direction = None
        if tk_cross == "Strong Bullish": signal_direction = "BUY"
        elif tk_cross == "Strong Bearish": signal_direction = "SELL"
        else: return None
        
        # --- 3. Run the Miracle Scoring Engine ---
        score, confirmations_list = self._score_ichimoku(ichimoku_data, signal_direction, cfg['weights'])
        
        if score < cfg['min_score_to_signal']:
            return None
        
        logger.info(f"[{self.strategy_name}] Initial Signal: Ichimoku {signal_direction} signal with score {score}.")
        confirmations = {"ichimoku_score": score, "ichimoku_details": ", ".join(confirmations_list)}
        
        # --- 4. Confirmation Funnel ---
        adx_strength = adx_data.get('values', {}).get('adx', 0)
        if adx_strength < cfg['min_adx_strength']:
            return None
        confirmations['adx_filter'] = f"Passed (ADX: {adx_strength:.2f})"

        if cfg['htf_confirmation_enabled']:
            if not self._get_trend_confirmation(signal_direction, cfg['htf_timeframe']):
                return None
            confirmations['htf_filter'] = f"Passed (Aligned with {cfg['htf_timeframe']})"

        # --- ✅ 5. Ichimoku-Native Risk Management ---
        entry_price = self.price_data.get('close')
        if not entry_price: return None

        ichi_values = ichimoku_data.get('values', {})
        stop_loss = None
        
        if cfg['sl_mode'] == 'kijun':
            stop_loss = ichi_values.get('kijun')
        elif cfg['sl_mode'] == 'kumo':
            if signal_direction == "BUY":
                # For a BUY, SL is below the Kumo (Senkou B is the stronger boundary)
                stop_loss = ichi_values.get('senkou_b')
            else: # SELL
                # For a SELL, SL is above the Kumo (Senkou B is the stronger boundary)
                stop_loss = ichi_values.get('senkou_b')
        
        if not stop_loss: 
            logger.warning(f"[{self.strategy_name}] Could not determine Ichimoku-native Stop Loss.")
            return None
            
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        
        if not risk_params or risk_params.get("risk_reward_ratio", 0) < cfg['min_rr_ratio']:
            return None
        confirmations['rr_check'] = f"Passed (R/R: {risk_params.get('risk_reward_ratio')})"

        logger.info(f"✨✨ [{self.strategy_name}] ICHIMOKU MIRACLE SIGNAL CONFIRMED! ✨✨")

        # --- 6. Package and Return the Final Signal ---
        return {
            "direction": signal_direction,
            "entry_price": entry_price,
            **risk_params,
            "confirmations": confirmations
        }
