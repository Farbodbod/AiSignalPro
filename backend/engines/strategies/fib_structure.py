import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

from .base_strategy import BaseStrategy

class ConfluenceSniper(BaseStrategy):
    """
    ConfluenceSniper - The Legendary, Unrivaled, World-Class Version
    -------------------------------------------------------------------
    This is a professional-grade reversal strategy based on the philosophy of
    high-confluence trading. It acts as a sniper, waiting patiently for the
    market to enter a meticulously defined Potential Reversal Zone (PRZ)
    and then firing only when multiple confirmation factors align.

    The Funnel:
    1.  PRZ Identification: Find and score zones where Fibonacci levels and
        market Structure (S/R) overlap.
    2.  Price Test: Wait for the price to enter the highest-scoring PRZ.
    3.  Confirmation 1 (Price Action): A strong candlestick reversal pattern must form.
    4.  Confirmation 2 (Momentum): Oscillators (RSI/Stoch) must confirm momentum exhaustion.
    5.  Confirmation 3 (HTF): The reversal is not fighting an overwhelmingly strong HTF trend.
    6.  Final Check: A pre-trade Risk-to-Reward check must pass.
    """
    strategy_name: str = "ConfluenceSniper"

    def _get_signal_config(self) -> Dict[str, Any]:
        """Loads and validates the strategy's specific parameters from the config."""
        return {
            "fib_levels_to_watch": self.config.get("fib_levels_to_watch", ["61.8%", "78.6%"]),
            "confluence_proximity_percent": float(self.config.get("confluence_proximity_percent", 0.3)), # 0.3%
            "atr_sl_multiplier": float(self.config.get("atr_sl_multiplier", 1.5)),
            "min_rr_ratio": float(self.config.get("min_risk_reward_ratio", 1.5)),
            "oscillator_confirmation_enabled": bool(self.config.get("oscillator_confirmation_enabled", True)),
            "htf_confirmation_enabled": bool(self.config.get("htf_confirmation_enabled", True)),
            "htf_timeframe": str(self.config.get("htf_timeframe", "4h")),
        }

    def _find_best_prz(self, direction: str) -> Optional[Dict[str, Any]]:
        """
        The Confluence Engine. Finds all Potential Reversal Zones (PRZ) where
        Fibonacci and Structure levels overlap, scores them, and returns the best one.
        """
        cfg = self._get_signal_config()
        fib_data = self.get_indicator('fibonacci')
        structure_data = self.get_indicator('structure')
        current_price = self.price_data.get('close')
        if not all([fib_data, structure_data, current_price]): return None

        # Safely extract levels from indicator analyses
        fib_levels = {lvl['level']: lvl['price'] for lvl in fib_data.get('levels', []) if 'Retracement' in lvl['type']}
        key_levels = structure_data.get('key_levels', {})
        target_sr_levels = key_levels.get('supports' if direction == "BUY" else 'resistances', [])
        
        confluence_zones = []
        for fib_level_str in cfg['fib_levels_to_watch']:
            fib_price = fib_levels.get(fib_level_str)
            if not fib_price: continue

            for sr_price in target_sr_levels:
                if abs(fib_price - sr_price) / (sr_price or 1) * 100 < cfg['confluence_proximity_percent']:
                    zone_price = (fib_price + sr_price) / 2.0
                    confluence_zones.append({
                        "price": zone_price, "fib_level": fib_level_str, "structure_level": sr_price,
                        "distance_to_price": abs(zone_price - current_price)
                    })
        
        # Return the zone closest to the current price
        return min(confluence_zones, key=lambda x: x['distance_to_price']) if confluence_zones else None

    def _get_oscillator_confirmation(self, direction: str) -> bool:
        """Checks if oscillators like RSI and Stochastic are in agreement."""
        rsi_data = self.get_indicator('rsi')
        stoch_data = self.get_indicator('stochastic')
        if not all([rsi_data, stoch_data]): return False

        rsi_val = rsi_data.get('values', {}).get('rsi')
        stoch_k = stoch_data.get('values', {}).get('k')
        if rsi_val is None or stoch_k is None: return False

        rsi_os = rsi_data.get('levels', {}).get('oversold', 30)
        rsi_ob = rsi_data.get('levels', {}).get('overbought', 70)
        stoch_os = stoch_data.get('analysis', {}).get('position') == 'Oversold'
        stoch_ob = stoch_data.get('analysis', {}).get('position') == 'Overbought'

        if direction == "BUY":
            return rsi_val < rsi_os and stoch_os
        elif direction == "SELL":
            return rsi_val > rsi_ob and stoch_ob
        return False

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self._get_signal_config()
        fib_data = self.get_indicator('fibonacci')
        if not fib_data: return None

        # --- 1. Determine Direction & Find Best PRZ ---
        swing_trend = fib_data.get('swing_trend')
        direction = "BUY" if swing_trend == "Up" else "SELL" if swing_trend == "Down" else None
        if not direction: return None

        best_prz = self._find_best_prz(direction)
        if not best_prz: return None

        # --- 2. Price Test Condition ---
        price_low, price_high = self.price_data.get('low'), self.price_data.get('high')
        is_testing = (direction == "BUY" and price_low and price_low <= best_prz['price']) or \
                     (direction == "SELL" and price_high and price_high >= best_prz['price'])
        if not is_testing: return None

        logger.info(f"[{self.strategy_name}] Price is testing a high-probability {direction} PRZ at {best_prz['price']:.5f}.")
        confirmations = {"confluence_zone": f"Fib {best_prz['fib_level']} & Structure at ~{best_prz['price']:.5f}"}

        # --- 3. Confirmation Funnel ---
        # Filter 1: Candlestick Confirmation
        confirming_pattern = self._get_candlestick_confirmation(direction, min_reliability='Strong')
        if not confirming_pattern:
            logger.info(f"[{self.strategy_name}] Signal REJECTED: No strong candlestick confirmation.")
            return None
        confirmations['candlestick_filter'] = f"Passed (Pattern: {confirming_pattern.get('name')})"

        # Filter 2: Oscillator Confirmation
        if cfg['oscillator_confirmation_enabled']:
            if not self._get_oscillator_confirmation(direction):
                logger.info(f"[{self.strategy_name}] Signal REJECTED: Lack of dual oscillator confirmation.")
                return None
            confirmations['oscillator_filter'] = "Passed (RSI & Stoch agree)"

        # Filter 3: Higher-Timeframe Confirmation
        if cfg['htf_confirmation_enabled']:
            # For a reversal, we want the HTF trend to NOT be strongly in the same direction
            if self._get_trend_confirmation(direction, cfg['htf_timeframe']):
                logger.info(f"[{self.strategy_name}] Signal REJECTED: Reversal attempt against a strong HTF trend.")
                return None
            confirmations['htf_filter'] = f"Passed (No strong opposing trend on {cfg['htf_timeframe']})"

        # --- 4. Risk Management & Final Checks ---
        entry_price = self.price_data.get('close')
        atr_data = self.get_indicator('atr')
        if not all([entry_price, atr_data]): return None

        atr_value = atr_data.get('values', {}).get('atr', entry_price * 0.01)
        structure_level = best_prz['structure_level']
        
        stop_loss = structure_level - (atr_value * cfg['atr_sl_multiplier']) if direction == "BUY" else structure_level + (atr_value * cfg['atr_sl_multiplier'])
            
        risk_params = self._calculate_smart_risk_management(entry_price, direction, stop_loss)
        if not risk_params or risk_params.get("risk_reward_ratio", 0) < cfg['min_rr_ratio']:
            logger.info(f"[{self.strategy_name}] Signal REJECTED: Initial R/R ratio is below threshold.")
            return None
        confirmations['rr_check'] = f"Passed (R/R: {risk_params.get('risk_reward_ratio')})"

        logger.info(f"✨✨ [{self.strategy_name}] CONFLUENCE SNIPER SIGNAL CONFIRMED! ✨✨")

        # --- 5. Package and Return the Legendary Signal ---
        return {
            "direction": direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations
        }
