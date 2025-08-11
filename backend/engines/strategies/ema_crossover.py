import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class EmaCrossoverStrategy(BaseStrategy):
    """
    EmaCrossoverStrategy - (v2.0 - Anti-Fragile Edition)
    -------------------------------------------------------------------
    This version is hardened against data failures. It fetches all required
    indicator data upfront and verifies its integrity before executing the
    core trading logic, making it robust and reliable.
    """
    strategy_name: str = "EmaCrossoverStrategy" # Corrected from Pro to match config keys

    def _get_signal_config(self) -> Dict[str, Any]:
        """Loads and validates the strategy's specific parameters from the config."""
        return {
            "min_adx_strength": float(self.config.get("min_adx_strength", 23.0)),
            "atr_sl_multiplier": float(self.config.get("atr_sl_multiplier", 2.5)),
            "htf_confirmation_enabled": bool(self.config.get("htf_confirmation_enabled", True)),
            "htf_timeframe": str(self.config.get("htf_timeframe", "4h")),
            "candlestick_confirmation_enabled": bool(self.config.get("candlestick_confirmation_enabled", True)),
        }

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self._get_signal_config()
        
        # --- ✅ 1. Anti-Fragile Data Check ---
        if not self.price_data:
            return None
            
        # Safely get all required indicator data.
        ema_cross_data = self.get_indicator('ema_cross')
        adx_data = self.get_indicator('adx')
        atr_data = self.get_indicator('atr')
        
        # The core logic requires these. If any fails, exit gracefully.
        if not all([ema_cross_data, adx_data, atr_data]):
            logger.debug(f"[{self.strategy_name}] Skipped: Missing one or more required indicators.")
            return None

        # --- 2. Get Primary Signal ---
        primary_signal = ema_cross_data.get('analysis', {}).get('signal')
        if primary_signal not in ["Buy", "Sell"]:
            return None
        
        signal_direction = primary_signal.upper()
        logger.info(f"[{self.strategy_name}] Initial Signal: {signal_direction} EMA Crossover found.")
        
        # --- 3. Apply Confirmation Filters (Logic is 100% preserved) ---
        ema_short = ema_cross_data.get('values', {}).get('short_period', 0)
        ema_long = ema_cross_data.get('values', {}).get('long_period', 0)
        confirmations = {"entry_trigger": f"EMA Cross ({ema_short}/{ema_long})"}

        adx_strength = adx_data.get('values', {}).get('adx', 0)
        if adx_strength < cfg['min_adx_strength']:
            return None
        confirmations['adx_filter'] = f"Passed (ADX: {adx_strength:.2f})"
        
        if cfg['htf_confirmation_enabled']:
            if not self._get_trend_confirmation(signal_direction, cfg['htf_timeframe']):
                return None
            confirmations['htf_filter'] = f"Passed (Aligned with {cfg['htf_timeframe']})"

        if cfg['candlestick_confirmation_enabled']:
            confirming_pattern = self._get_candlestick_confirmation(signal_direction, min_reliability='Medium')
            if not confirming_pattern:
                return None
            confirmations['candlestick_filter'] = f"Passed (Pattern: {confirming_pattern.get('name')})"

        logger.info(f"✨✨ [{self.strategy_name}] Signal for {signal_direction} confirmed by all filters! ✨✨")

        # --- 4. Calculate Risk Management (Logic is 100% preserved) ---
        entry_price = self.price_data.get('close')
        long_ema_val = ema_cross_data.get('values', {}).get('long_ema')
        if not all([entry_price, long_ema_val]): return None
            
        atr_value = atr_data.get('values', {}).get('atr', 0)
        
        stop_loss = 0
        if signal_direction == "BUY":
            stop_loss = long_ema_val - (atr_value * cfg['atr_sl_multiplier'])
        else: # SELL
            stop_loss = long_ema_val + (atr_value * cfg['atr_sl_multiplier'])

        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        if not risk_params or not risk_params.get("targets"):
             return None

        # --- 5. Package and Return the Final Signal ---
        return {
            "direction": signal_direction,
            "entry_price": entry_price,
            **risk_params,
            "confirmations": confirmations
        }
