import logging
from typing import Dict, Any, Optional, Tuple
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class WhaleReversal(BaseStrategy):
    """
    WhaleReversal - The Legendary, Unrivaled, World-Class Version
    --------------------------------------------------------------
    This is a high-precision reversal strategy that hunts for signs of
    absorption or distribution by smart money (whales) at key market
    structure levels.

    The Funnel (The Triple Confluence):
    1.  Location: The price must be actively testing a key support or resistance level.
    2.  Force: A significant volume spike (Whale Activity) must occur at this level,
        with pressure opposing the current price move (e.g., buying pressure at support).
    3.  Timing: A strong candlestick reversal pattern must form as the final entry trigger.
    """
    strategy_name: str = "WhaleReversal"

    def _get_signal_config(self) -> Dict[str, Any]:
        """Loads and validates the strategy's specific parameters from the config."""
        return {
            "proximity_percent": float(self.config.get("proximity_percent", 0.5)),  # 0.5% distance from the level
            "atr_sl_multiplier": float(self.config.get("atr_sl_multiplier", 1.5)),
            "min_rr_ratio": float(self.config.get("min_risk_reward_ratio", 1.5)),
            "htf_confirmation_enabled": bool(self.config.get("htf_confirmation_enabled", True)),
            "htf_timeframe": str(self.config.get("htf_timeframe", "4h")),
        }

    def _find_tested_level(self, cfg: Dict[str, Any]) -> Optional[Tuple[str, float]]:
        """
        Finds the closest key Support or Resistance level that the current
        price is actively testing.
        Returns: (direction, level_price) or (None, None)
        """
        structure_data = self.get_indicator('structure')
        if not structure_data or 'analysis' not in structure_data: return None, None
        
        price_low = self.price_data.get('low'); price_high = self.price_data.get('high')
        if not all([price_low, price_high]): return None, None

        # Check for support test
        nearest_support = structure_data['analysis']['proximity'].get('nearest_support')
        if nearest_support and abs(price_low - nearest_support) / nearest_support * 100 < cfg['proximity_percent']:
            return "BUY", nearest_support

        # Check for resistance test
        nearest_resistance = structure_data['analysis']['proximity'].get('nearest_resistance')
        if nearest_resistance and abs(price_high - nearest_resistance) / nearest_resistance * 100 < cfg['proximity_percent']:
            return "SELL", nearest_resistance
            
        return None, None

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self._get_signal_config()

        # --- 1. Location: Find a Tested Key Level ---
        signal_direction, tested_level = self._find_tested_level(cfg)
        if not signal_direction:
            return None
        
        logger.info(f"[{self.strategy_name}] Location Confirmed: Price is testing a key {'Support' if signal_direction == 'BUY' else 'Resistance'} at {tested_level:.5f}.")
        confirmations = {"location_confirmation": f"Tested key S/R at {tested_level:.5f}"}

        # --- 2. Force: Confirm with Whale Activity ---
        whales_data = self.get_indicator('whales')
        if not whales_data or not whales_data.get('analysis', {}).get('is_whale_activity'):
            logger.info(f"[{self.strategy_name}] Signal REJECTED: No whale activity detected at the key level.")
            return None
        
        # This is the core of the strategy: pressure must oppose the move, indicating absorption/distribution
        whale_pressure = whales_data['analysis'].get('pressure')
        is_absorption = (signal_direction == "BUY" and "Buying" in whale_pressure)
        is_distribution = (signal_direction == "SELL" and "Selling" in whale_pressure)

        if not (is_absorption or is_distribution):
            logger.info(f"[{self.strategy_name}] Signal REJECTED: Whale pressure ({whale_pressure}) does not confirm a reversal.")
            return None
        confirmations['force_confirmation'] = f"Passed (Whale {whale_pressure} detected)"
        
        # --- 3. Timing: Confirm with Candlestick Pattern ---
        confirming_pattern = self._get_candlestick_confirmation(signal_direction, min_reliability='Strong')
        if not confirming_pattern:
            logger.info(f"[{self.strategy_name}] Signal REJECTED: No strong candlestick reversal pattern found.")
            return None
        confirmations['timing_confirmation'] = f"Passed (Pattern: {confirming_pattern.get('name')})"

        # --- Optional Filter: Higher-Timeframe Confirmation ---
        if cfg['htf_confirmation_enabled']:
            # For a reversal, we want the HTF trend to NOT be strongly aligned
            if self._get_trend_confirmation(signal_direction, cfg['htf_timeframe']):
                logger.info(f"[{self.strategy_name}] Signal REJECTED: Reversal attempt against a strong HTF trend.")
                return None
            confirmations['htf_filter'] = f"Passed (No strong opposing trend on {cfg['htf_timeframe']})"

        # --- 4. Risk Management & Final Checks ---
        entry_price = self.price_data.get('close')
        atr_data = self.get_indicator('atr')
        if not all([entry_price, atr_data]): return None

        atr_value = atr_data.get('values', {}).get('atr', entry_price * 0.01)
        
        # Stop loss is placed logically on the other side of the tested level, cushioned by ATR
        if signal_direction == "BUY":
            stop_loss = tested_level - (atr_value * cfg['atr_sl_multiplier'])
        else: # SELL
            stop_loss = tested_level + (atr_value * cfg['atr_sl_multiplier'])
            
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        
        if not risk_params or risk_params.get("risk_reward_ratio", 0) < cfg['min_rr_ratio']:
            logger.info(f"[{self.strategy_name}] Signal REJECTED: Initial R/R ratio is below threshold.")
            return None
        confirmations['rr_check'] = f"Passed (R/R: {risk_params.get('risk_reward_ratio')})"

        logger.info(f"✨✨ [{self.strategy_name}] WHALE REVERSAL SIGNAL CONFIRMED! ✨✨")

        # --- 5. Package and Return the Legendary Signal ---
        return {
            "direction": signal_direction,
            "entry_price": entry_price,
            **risk_params,
            "confirmations": confirmations
        }
