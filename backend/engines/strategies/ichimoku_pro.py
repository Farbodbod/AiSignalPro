import logging
from typing import Dict, Any, Optional, List
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class IchimokuHybridPro(BaseStrategy):
    """
    IchimokuHybridPro - The Legendary, World-Class, Toolkit-Powered Version
    -------------------------------------------------------------------------
    This is an advanced, multi-faceted trading strategy engine. It operates on a
    sophisticated, configurable scoring system based on the Ichimoku Kinko Hyo.
    
    The Funnel:
    1.  Scoring: An Ichimoku signal must achieve a minimum score to be considered.
    2.  Filter 1 (Trend Strength): The signal is validated against ADX.
    3.  Filter 2 (Structural Alignment): The stop loss placement, determined by
        ZigZag pivots, must align with the signal's direction.
    4.  Filter 3 (Optional HTF): The signal can be validated against the HTF trend.
    5.  Risk Management: A pre-trade R/R check is performed.
    """
    strategy_name: str = "IchimokuHybridPro"

    def _get_signal_config(self) -> Dict[str, Any]:
        """Loads and validates the strategy's specific parameters from the config."""
        # Default weights for the scoring system
        default_weights = {
            "price_above_kumo": 3, "tk_cross": 2, "chikou": 1,
            "price_kijun": 1, "future_kumo": 1
        }
        return {
            "min_score_to_signal": int(self.config.get("min_score_to_signal", 5)),
            "min_adx_strength": float(self.config.get("min_adx_strength", 23.0)),
            "atr_sl_multiplier": float(self.config.get("atr_sl_multiplier", 1.0)),
            "min_rr_ratio": float(self.config.get("min_risk_reward_ratio", 1.2)),
            "weights": self.config.get("weights", default_weights),
            "htf_confirmation_enabled": bool(self.config.get("htf_confirmation_enabled", False)),
            "htf_timeframe": str(self.config.get("htf_timeframe", "4h")),
        }

    def _score_ichimoku(self, ichimoku_data: Dict[str, Any], weights: Dict[str, int]) -> tuple[int, int, List[str]]:
        """Calculates bullish and bearish scores based on Ichimoku components."""
        buy_score, sell_score, confirmations = 0, 0, []
        
        analysis = ichimoku_data.get('analysis', {})
        values = ichimoku_data.get('values', {})
        
        price_pos = analysis.get('price_position')
        tk_cross = analysis.get('tk_cross')
        chikou_conf = analysis.get('chikou_confirmation')
        
        # Scoring based on analysis fields
        if price_pos == "Above Kumo": buy_score += weights.get('price_above_kumo', 3); confirmations.append("Price Above Kumo")
        elif price_pos == "Below Kumo": sell_score += weights.get('price_above_kumo', 3); confirmations.append("Price Below Kumo")

        if "Bullish" in tk_cross: buy_score += weights.get('tk_cross', 2); confirmations.append(tk_cross)
        elif "Bearish" in tk_cross: sell_score += weights.get('tk_cross', 2); confirmations.append(tk_cross)
        
        if chikou_conf == "Bullish": buy_score += weights.get('chikou', 1); confirmations.append("Chikou Confirmed Bullish")
        elif chikou_conf == "Bearish": sell_score += weights.get('chikou', 1); confirmations.append("Chikou Confirmed Bearish")

        # Scoring based on raw values
        price = self.price_data.get('close')
        kijun = values.get('kijun')
        senkou_a = values.get('senkou_a')
        senkou_b = values.get('senkou_b')

        if all([price, kijun]):
            if price > kijun: buy_score += weights.get('price_kijun', 1); confirmations.append("Price > Kijun")
            elif price < kijun: sell_score += weights.get('price_kijun', 1); confirmations.append("Price < Kijun")
        
        if all([senkou_a, senkou_b]):
            if senkou_a > senkou_b: buy_score += weights.get('future_kumo', 1); confirmations.append("Future Kumo Bullish")
            elif senkou_a < senkou_b: sell_score += weights.get('future_kumo', 1); confirmations.append("Future Kumo Bearish")

        return buy_score, sell_score, confirmations

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self._get_signal_config()
        
        # --- 1. Get Required Data using the Toolkit ---
        ichimoku_data = self.get_indicator('ichimoku'); adx_data = self.get_indicator('adx')
        structure_data = self.get_indicator('structure'); atr_data = self.get_indicator('atr')
        
        if not all([ichimoku_data, adx_data, structure_data, atr_data, self.price_data]): return None

        # --- 2. Run the Ichimoku Scoring Engine ---
        buy_score, sell_score, confirmations_list = self._score_ichimoku(ichimoku_data, cfg['weights'])
        
        signal_direction, score = (None, 0)
        if buy_score >= cfg['min_score_to_signal']: signal_direction, score = "BUY", buy_score
        elif sell_score >= cfg['min_score_to_signal']: signal_direction, score = "SELL", sell_score
        else: return None
        
        logger.info(f"[{self.strategy_name}] Initial Signal: Ichimoku {signal_direction} signal with score {score}.")
        confirmations = {"ichimoku_score": score, "ichimoku_details": ", ".join(confirmations_list)}
        
        # --- 3. Confirmation Funnel ---
        # Filter 1: ADX Trend Strength
        adx_strength = adx_data.get('values', {}).get('adx', 0)
        if adx_strength < cfg['min_adx_strength']:
            logger.info(f"[{self.strategy_name}] Signal REJECTED: ADX strength ({adx_strength:.2f}) is below threshold.")
            return None
        confirmations['adx_filter'] = f"Passed (ADX: {adx_strength:.2f})"

        # Filter 2: Higher-Timeframe Trend Confirmation (Optional)
        if cfg['htf_confirmation_enabled']:
            if not self._get_trend_confirmation(signal_direction, cfg['htf_timeframe']):
                logger.info(f"[{self.strategy_name}] Signal REJECTED: Not aligned with {cfg['htf_timeframe']} trend.")
                return None
            confirmations['htf_filter'] = f"Passed (Aligned with {cfg['htf_timeframe']})"

        # --- 4. Calculate Risk & Perform Pre-Trade Checks ---
        entry_price = self.price_data.get('close')
        
        # Stop Loss is based on the last valid structural pivot
        last_pivot = structure_data.get('analysis', {}).get('last_pivot')
        if not last_pivot: logger.warning(f"[{self.strategy_name}] Could not find a ZigZag pivot for SL."); return None
        
        # Structural Alignment Check
        if (signal_direction == "BUY" and last_pivot['type'] != 'Support') or \
           (signal_direction == "SELL" and last_pivot['type'] != 'Resistance'):
           logger.info(f"[{self.strategy_name}] Signal REJECTED: Last pivot ({last_pivot['type']}) does not support a {signal_direction} signal.")
           return None
        
        pivot_price = last_pivot.get('price')
        atr_value = atr_data.get('values', {}).get('atr')
        if not all([entry_price, pivot_price, atr_value]): return None
        
        stop_loss = pivot_price - (atr_value * cfg['atr_sl_multiplier']) if signal_direction == "BUY" else pivot_price + (atr_value * cfg['atr_sl_multiplier'])
        
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        
        # Final R/R Check
        if not risk_params or risk_params.get("risk_reward_ratio", 0) < cfg['min_rr_ratio']:
            logger.info(f"[{self.strategy_name}] Signal REJECTED: Initial R/R ratio is below threshold.")
            return None
        confirmations['rr_check'] = f"Passed (R/R: {risk_params.get('risk_reward_ratio')})"

        logger.info(f"✨✨ [{self.strategy_name}] ICHIMOKU HYBRID SIGNAL CONFIRMED! ✨✨")

        # --- 5. Package and Return the Final Signal ---
        return {
            "direction": signal_direction,
            "entry_price": entry_price,
            **risk_params,
            "confirmations": confirmations
        }
