import logging
from typing import Dict, Any, Optional, List
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class DivergenceSniperPro(BaseStrategy):
    """
    DivergenceSniperPro - Definitive, World-Class, Toolkit-Powered Version
    -----------------------------------------------------------------------
    This is a high-precision reversal strategy. It uses a "Confirmation Funnel"
    to validate a raw divergence signal against multiple market context layers,
    producing high-probability trading signals.
    
    The Funnel:
    1.  Signal: Find a strong Regular Divergence.
    2.  Filter 1 (Structure): Confirm the divergence occurred near a key S/R level.
    3.  Filter 2 (HTF Trend): Ensure the signal is not fighting a strong higher-timeframe trend.
    4.  Filter 3 (Volume): Confirm significant whale activity supports the move.
    5.  Trigger: Use Williams %R exiting OB/OS zones as the final momentum trigger for entry.
    """
    strategy_name: str = "DivergenceSniperPro"

    def _get_signal_config(self) -> Dict[str, Any]:
        """Loads and validates the strategy's specific parameters from the config."""
        return {
            "htf_confirmation_enabled": self.config.get("htf_confirmation_enabled", True),
            "htf_timeframe": self.config.get("htf_timeframe", "4h"),
            "volume_confirmation_enabled": self.config.get("volume_confirmation_enabled", True),
            "candlestick_confirmation_enabled": self.config.get("candlestick_confirmation_enabled", True),
            "atr_sl_multiplier": self.config.get("atr_sl_multiplier", 1.0)
        }

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self._get_signal_config()
        
        # --- Funnel Step 1: Find a valid Divergence Signal ---
        divergence_data = self.get_indicator('divergence')
        if not divergence_data or not divergence_data.get('analysis', {}).get('signals'):
            return None

        # We are interested in "Regular" divergences for reversals
        potential_signals = [
            s for s in divergence_data['analysis']['signals'] 
            if "Regular" in s.get('type', '')
        ]
        if not potential_signals:
            return None

        divergence = potential_signals[0] # Take the most recent one
        signal_direction = "BUY" if "Bullish" in divergence['type'] else "SELL"
        logger.info(f"[{self.strategy_name}] Initial Signal: Found {divergence['type']}.")
        
        # --- Funnel Step 2: Structure Confirmation (S/R Confluence) ---
        structure_data = self.get_indicator('structure')
        if not structure_data: return None
        price_position = structure_data.get('analysis', {}).get('position')
        
        is_at_support = "Support" in price_position if price_position else False
        is_at_resistance = "Resistance" in price_position if price_position else False

        if (signal_direction == "BUY" and not is_at_support) or \
           (signal_direction == "SELL" and not is_at_resistance):
            logger.info(f"[{self.strategy_name}] Signal REJECTED: Divergence is not at a key support/resistance zone.")
            return None
        confirmations = {"divergence_type": divergence['type'], "structure_confirmation": f"Confirmed at {price_position}"}

        # --- Funnel Step 3: Higher-Timeframe Trend Filter (Optional) ---
        if cfg['htf_confirmation_enabled']:
            if self._get_trend_confirmation(signal_direction, cfg['htf_timeframe']):
                logger.info(f"[{self.strategy_name}] Signal REJECTED: Divergence is against a strong HTF trend ({cfg['htf_timeframe']}).")
                return None # Note: For reversals, we want the HTF trend to NOT be strongly aligned
            confirmations['htf_filter'] = f"Passed (No strong opposing trend on {cfg['htf_timeframe']})"

        # --- Funnel Step 4: Volume Confirmation (Optional) ---
        if cfg['volume_confirmation_enabled']:
            if not self._get_volume_confirmation():
                logger.info(f"[{self.strategy_name}] Signal REJECTED: Lacks significant volume spike.")
                return None
            confirmations['volume_filter'] = "Passed (Whale activity detected)"

        # --- Funnel Step 5: Candlestick Confirmation (Optional) ---
        if cfg['candlestick_confirmation_enabled']:
            confirming_pattern = self._get_candlestick_confirmation(signal_direction, min_reliability='Strong')
            if not confirming_pattern:
                logger.info(f"[{self.strategy_name}] Signal REJECTED: No strong confirming candlestick pattern.")
                return None
            confirmations['candlestick_filter'] = f"Passed (Pattern: {confirming_pattern.get('name')})"

        # --- Final Trigger: Williams %R Momentum ---
        wr_data = self.get_indicator('williams_r')
        if not wr_data: return None
        wr_signal = wr_data.get('analysis', {}).get('crossover_signal', 'Hold')
        
        trigger_fired = (signal_direction == "BUY" and "Buy" in wr_signal) or \
                        (signal_direction == "SELL" and "Sell" in wr_signal)
        
        if not trigger_fired:
            logger.info(f"[{self.strategy_name}] Signal PENDING: All confirmations met, awaiting Williams %R momentum trigger.")
            return None

        logger.info(f"✨✨ [{self.strategy_name}] DIVERGENCE SNIPER SIGNAL CONFIRMED! ✨✨")

        # --- Risk Management ---
        entry_price = self.price_data.get('close')
        atr_data = self.get_indicator('atr')
        if not entry_price or not atr_data: return None
        
        # Use the price of the pivot that formed the divergence for a safer Stop Loss
        pivot_price = divergence.get('pivots', [{}, {}])[1].get('price')
        if not pivot_price: return None # Should not happen

        atr_value = atr_data.get('values', {}).get('atr', entry_price * 0.01)
        
        if signal_direction == "BUY":
            stop_loss = pivot_price - (atr_value * cfg['atr_sl_multiplier'])
        else: # SELL
            stop_loss = pivot_price + (atr_value * cfg['atr_sl_multiplier'])

        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        if not risk_params or not risk_params.get("targets"):
             logger.info(f"[{self.strategy_name}] Signal REJECTED: Could not calculate valid risk/reward targets.")
             return None
        
        # --- Package and Return the Final Signal ---
        return {
            "direction": signal_direction,
            "entry_price": entry_price,
            **risk_params,
            "confirmations": confirmations
        }
