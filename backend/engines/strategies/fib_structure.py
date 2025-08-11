import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

from .base_strategy import BaseStrategy

class ConfluenceSniper(BaseStrategy):
    """
    ConfluenceSniper - (v2.0 - Anti-Fragile Edition)
    -------------------------------------------------------------------
    This version is hardened against data failures. It fetches all required
    indicator data upfront and verifies its integrity before executing the
    core trading logic, making it robust and reliable.
    """
    strategy_name: str = "ConfluenceSniper"

    def _get_signal_config(self) -> Dict[str, Any]:
        """Loads and validates the strategy's specific parameters from the config."""
        return {
            "fib_levels_to_watch": self.config.get("fib_levels_to_watch", ["61.8%", "78.6%"]),
            "confluence_proximity_percent": float(self.config.get("confluence_proximity_percent", 0.3)),
            "atr_sl_multiplier": float(self.config.get("atr_sl_multiplier", 1.5)),
            "min_rr_ratio": float(self.config.get("min_risk_reward_ratio", 1.5)),
            "oscillator_confirmation_enabled": bool(self.config.get("oscillator_confirmation_enabled", True)),
            "htf_confirmation_enabled": bool(self.config.get("htf_confirmation_enabled", True)),
            "htf_timeframe": str(self.config.get("htf_timeframe", "4h")),
        }

    def _find_best_prz(self, cfg: Dict[str, Any], fib_data: Dict[str, Any], structure_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """The Confluence Engine. Finds and returns the best Potential Reversal Zone."""
        current_price = self.price_data.get('close')
        if not current_price: return None

        fib_levels = {lvl['level']: lvl['price'] for lvl in fib_data.get('levels', []) if 'Retracement' in lvl['type']}
        key_levels = structure_data.get('key_levels', {})
        swing_trend = fib_data.get('swing_trend')
        target_sr_levels = key_levels.get('supports' if swing_trend == "Up" else 'resistances', [])
        
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
        
        return min(confluence_zones, key=lambda x: x['distance_to_price']) if confluence_zones else None

    def _get_oscillator_confirmation(self, direction: str, rsi_data: Dict[str, Any], stoch_data: Dict[str, Any]) -> bool:
        """Checks if oscillators like RSI and Stochastic are in agreement."""
        rsi_val = rsi_data.get('values', {}).get('rsi')
        stoch_k = stoch_data.get('values', {}).get('k')
        if rsi_val is None or stoch_k is None: return False

        rsi_os = rsi_data.get('levels', {}).get('oversold', 30)
        rsi_ob = rsi_data.get('levels', {}).get('overbought', 70)
        stoch_pos = stoch_data.get('analysis', {}).get('position')

        if direction == "BUY":
            return rsi_val < rsi_os and stoch_pos == 'Oversold'
        elif direction == "SELL":
            return rsi_val > rsi_ob and stoch_pos == 'Overbought'
        return False

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self._get_signal_config()

        # --- ✅ 1. Anti-Fragile Data Check ---
        if not self.price_data:
            return None

        fib_data = self.get_indicator('fibonacci')
        structure_data = self.get_indicator('structure')
        rsi_data = self.get_indicator('rsi')
        stoch_data = self.get_indicator('stochastic')
        atr_data = self.get_indicator('atr')

        if not all([fib_data, structure_data, rsi_data, stoch_data, atr_data]):
            logger.debug(f"[{self.strategy_name}] Skipped: Missing one or more required indicators.")
            return None

        # --- 2. Determine Direction & Find Best PRZ ---
        swing_trend = fib_data.get('swing_trend')
        direction = "BUY" if swing_trend == "Up" else "SELL" if swing_trend == "Down" else None
        if not direction: return None

        best_prz = self._find_best_prz(cfg, fib_data, structure_data)
        if not best_prz: return None

        # --- 3. Price Test Condition (Logic is 100% preserved) ---
        price_low, price_high = self.price_data.get('low'), self.price_data.get('high')
        is_testing = (direction == "BUY" and price_low and price_low <= best_prz['price']) or \
                     (direction == "SELL" and price_high and price_high >= best_prz['price'])
        if not is_testing: return None

        logger.info(f"[{self.strategy_name}] Price is testing a high-probability {direction} PRZ at {best_prz['price']:.5f}.")
        confirmations = {"confluence_zone": f"Fib {best_prz['fib_level']} & Structure at ~{best_prz['price']:.5f}"}

        # --- 4. Confirmation Funnel (Logic is 100% preserved) ---
        confirming_pattern = self._get_candlestick_confirmation(direction, min_reliability='Strong')
        if not confirming_pattern:
            return None
        confirmations['candlestick_filter'] = f"Passed (Pattern: {confirming_pattern.get('name')})"

        if cfg['oscillator_confirmation_enabled']:
            if not self._get_oscillator_confirmation(direction, rsi_data, stoch_data):
                return None
            confirmations['oscillator_filter'] = "Passed (RSI & Stoch agree)"

        if cfg['htf_confirmation_enabled']:
            if self._get_trend_confirmation(direction, cfg['htf_timeframe']):
                return None
            confirmations['htf_filter'] = f"Passed (No strong opposing trend on {cfg['htf_timeframe']})"

        # --- 5. Risk Management & Final Checks (Logic is 100% preserved) ---
        entry_price = self.price_data.get('close')
        if not entry_price: return None

        atr_value = atr_data.get('values', {}).get('atr', entry_price * 0.01)
        structure_level = best_prz['structure_level']
        
        stop_loss = structure_level - (atr_value * cfg['atr_sl_multiplier']) if direction == "BUY" else structure_level + (atr_value * cfg['atr_sl_multiplier'])
            
        risk_params = self._calculate_smart_risk_management(entry_price, direction, stop_loss)
        if not risk_params or risk_params.get("risk_reward_ratio", 0) < cfg['min_rr_ratio']:
            return None
        confirmations['rr_check'] = f"Passed (R/R: {risk_params.get('risk_reward_ratio')})"

        logger.info(f"✨✨ [{self.strategy_name}] CONFLUENCE SNIPER SIGNAL CONFIRMED! ✨✨")

        # --- 6. Package and Return the Legendary Signal ---
        return {
            "direction": direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations
        }
