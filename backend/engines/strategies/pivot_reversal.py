import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

from .base_strategy import BaseStrategy

class PivotConfluenceSniper(BaseStrategy):
    """
    PivotConfluenceSniper - The Legendary, World-Class, Toolkit-Powered Version
    ----------------------------------------------------------------------------
    This is a high-precision mean-reversion and reversal strategy. It embodies the
    philosophy of confluence trading.

    The Funnel:
    1.  Zone Identification: Find high-probability reversal zones where mathematical
        Pivot Points coincide with historical price Structure (S/R levels).
    2.  Price Test: Wait for the price to actively test one of these powerful zones.
    3.  Filter 1 (Dual Oscillator): Confirm the test with simultaneous Overbought/Oversold
        readings from both Stochastic and CCI.
    4.  Filter 2 (Price Action): Require a confirming candlestick reversal pattern
        at the zone.
    5.  Risk Management: Place Stop Loss logically behind the confluence structure.
    """
    strategy_name: str = "PivotConfluenceSniper"

    def _get_signal_config(self) -> Dict[str, Any]:
        """Loads and validates the strategy's specific parameters from the config."""
        return {
            "pivot_levels_to_check": self.config.get("pivot_levels_to_check", ['R2', 'R1', 'S1', 'S2']),
            "confluence_proximity_percent": float(self.config.get("confluence_proximity_percent", 0.3)), # 0.3%
            "stoch_oversold": float(self.config.get("stoch_oversold", 25.0)),
            "stoch_overbought": float(self.config.get("stoch_overbought", 75.0)),
            "cci_oversold": float(self.config.get("cci_oversold", -100.0)),
            "cci_overbought": float(self.config.get("cci_overbought", 100.0)),
            "atr_sl_multiplier": float(self.config.get("atr_sl_multiplier", 1.2)),
            "min_rr_ratio": float(self.config.get("min_risk_reward_ratio", 1.5)),
        }

    def _find_best_confluence_zone(self, direction: str) -> Optional[Dict[str, Any]]:
        """
        Finds all confluence zones and returns the one closest to the current price.
        """
        cfg = self._get_signal_config()
        pivots_data = self.get_indicator('pivots')
        structure_data = self.get_indicator('structure')
        current_price = self.price_data.get('close')

        if not all([pivots_data, structure_data, current_price]): return None

        pivot_levels = {lvl['level']: lvl['price'] for lvl in pivots_data.get('levels', [])}
        key_levels = structure_data.get('key_levels', {})
        
        target_pivot_names = [p for p in cfg['pivot_levels_to_check'] if (p.startswith('S') if direction == "BUY" else p.startswith('R'))]
        target_structures = key_levels.get('supports' if direction == "BUY" else 'resistances', [])
        
        confluence_zones = []
        for pivot_name in target_pivot_names:
            pivot_price = pivot_levels.get(pivot_name)
            if not pivot_price: continue
            for struct_price in target_structures:
                # Safe division and proximity check
                if abs(pivot_price - struct_price) / (struct_price or 1) * 100 < cfg['confluence_proximity_percent']:
                    zone_price = (pivot_price + struct_price) / 2.0
                    confluence_zones.append({
                        "price": zone_price,
                        "pivot_name": pivot_name,
                        "structure_price": struct_price,
                        "distance_to_price": abs(zone_price - current_price)
                    })
        
        # Return the zone with the minimum distance to the current price
        return min(confluence_zones, key=lambda x: x['distance_to_price']) if confluence_zones else None

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self._get_signal_config()

        # --- 1. Zone Identification & Price Test ---
        buy_zone = self._find_best_confluence_zone("BUY")
        sell_zone = self._find_best_confluence_zone("SELL")
        price_low, price_high = self.price_data.get('low'), self.price_data.get('high')
        
        signal_direction, zone_info = None, None
        if buy_zone and price_low and price_low <= buy_zone['price']:
            signal_direction, zone_info = "BUY", buy_zone
        elif sell_zone and price_high and price_high >= sell_zone['price']:
            signal_direction, zone_info = "SELL", sell_zone
        else:
            return None
        
        logger.info(f"[{self.strategy_name}] Potential Signal: Price tested a {signal_direction} confluence zone at {zone_info['price']:.5f}.")
        confirmations = {"confluence_zone": f"Pivot {zone_info['pivot_name']} & Structure at ~{zone_info['price']:.5f}"}

        # --- 2. Confirmation Funnel ---
        # Filter 1: Dual Oscillator Confirmation
        stoch_data = self.get_indicator('stochastic')
        cci_data = self.get_indicator('cci')
        if not all([stoch_data, cci_data]): return None

        stoch_k = stoch_data.get('values', {}).get('k')
        cci_val = cci_data.get('values', {}).get('value')
        if stoch_k is None or cci_val is None: return None

        osc_confirmed = False
        if signal_direction == "BUY" and stoch_k < cfg['stoch_oversold'] and cci_val < cfg['cci_oversold']:
            osc_confirmed = True
        elif signal_direction == "SELL" and stoch_k > cfg['stoch_overbought'] and cci_val > cfg['cci_overbought']:
            osc_confirmed = True

        if not osc_confirmed:
            logger.info(f"[{self.strategy_name}] Signal REJECTED: Lack of oscillator confirmation.")
            return None
        confirmations['oscillator_filter'] = f"Passed (Stoch: {stoch_k:.2f}, CCI: {cci_val:.2f})"

        # Filter 2: Candlestick Confirmation
        confirming_pattern = self._get_candlestick_confirmation(signal_direction, min_reliability='Strong')
        if not confirming_pattern:
            logger.info(f"[{self.strategy_name}] Signal REJECTED: No strong candlestick confirmation pattern.")
            return None
        confirmations['candlestick_filter'] = f"Passed (Pattern: {confirming_pattern.get('name')})"

        # --- 3. Risk Management & Final Checks ---
        entry_price = self.price_data.get('close')
        atr_data = self.get_indicator('atr')
        if not all([entry_price, atr_data]): return None

        atr_value = atr_data.get('values', {}).get('atr', entry_price * 0.01)
        structure_level = zone_info['structure_price']
        
        stop_loss = structure_level - (atr_value * cfg['atr_sl_multiplier']) if signal_direction == "BUY" else structure_level + (atr_value * cfg['atr_sl_multiplier'])
            
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        
        # Pre-Trade R/R Check
        if not risk_params or risk_params.get("risk_reward_ratio", 0) < cfg['min_rr_ratio']:
            logger.info(f"[{self.strategy_name}] Signal REJECTED: Initial R/R ratio is below threshold.")
            return None
        confirmations['rr_check'] = f"Passed (R/R: {risk_params.get('risk_reward_ratio')})"

        # Optional: Set first target to the Central Pivot
        pivots_data = self.get_indicator('pivots')
        pivot_p_level = next((lvl['price'] for lvl in pivots_data.get('levels', []) if lvl['level'] == 'P'), None)
        if pivot_p_level and risk_params.get('targets'):
            risk_params['targets'][0] = pivot_p_level
            confirmations['target_adjustment'] = "TP1 set to Central Pivot"
            
        logger.info(f"✨✨ [{self.strategy_name}] PIVOT SNIPER SIGNAL CONFIRMED! ✨✨")

        # --- 4. Package and Return the Legendary Signal ---
        return {
            "direction": signal_direction,
            "entry_price": entry_price,
            **risk_params,
            "confirmations": confirmations
        }
