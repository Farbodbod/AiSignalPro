import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class KeltnerMomentumBreakout(BaseStrategy):
    """
    KeltnerMomentumBreakout - (v2.0 - Anti-Fragile Edition)
    -------------------------------------------------------------------------
    This version is hardened against data failures. It fetches all required
    indicator data upfront and verifies its integrity before executing the
    core trading logic, making it robust and reliable.
    """
    strategy_name: str = "KeltnerMomentumBreakout"

    def _get_signal_config(self) -> Dict[str, Any]:
        """Loads and validates the strategy's specific parameters from the config."""
        return {
            "min_adx_strength": float(self.config.get("min_adx_strength", 25.0)),
            "cci_threshold": float(self.config.get("cci_threshold", 100.0)),
            "min_rr_ratio": float(self.config.get("min_risk_reward_ratio", 1.5)),
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
        keltner_data = self.get_indicator('keltner_channel')
        adx_data = self.get_indicator('adx')
        cci_data = self.get_indicator('cci')
        
        # The core logic requires these three. If any fails, exit gracefully.
        if not all([keltner_data, adx_data, cci_data]):
            logger.debug(f"[{self.strategy_name}] Skipped: Missing one or more required indicators.")
            return None

        # --- 2. Get Primary Signal from Keltner Channel Breakout ---
        keltner_pos = keltner_data.get('analysis', {}).get('position')
        signal_direction = None
        if "Breakout Above" in keltner_pos: signal_direction = "BUY"
        elif "Breakdown Below" in keltner_pos: signal_direction = "SELL"
        else: return None
        
        logger.info(f"[{self.strategy_name}] Initial Signal: {signal_direction} from Keltner Channel breakout.")
        confirmations = {"entry_trigger": "Keltner Channel Breakout"}

        # --- 3. Confirmation Funnel (Logic is 100% preserved) ---
        adx_strength = adx_data.get('values', {}).get('adx', 0)
        if adx_strength < cfg['min_adx_strength']:
            return None
        confirmations['adx_filter'] = f"Passed (ADX: {adx_strength:.2f})"

        cci_value = cci_data.get('values', {}).get('value', 0)
        cci_confirmed = False
        if signal_direction == "BUY" and cci_value > cfg['cci_threshold']: cci_confirmed = True
        elif signal_direction == "SELL" and cci_value < -cfg['cci_threshold']: cci_confirmed = True
        if not cci_confirmed:
            return None
        confirmations['cci_filter'] = f"Passed (CCI: {cci_value:.2f})"

        if cfg['htf_confirmation_enabled']:
            if not self._get_trend_confirmation(signal_direction, cfg['htf_timeframe']):
                return None
            confirmations['htf_filter'] = f"Passed (Aligned with {cfg['htf_timeframe']})"
        
        if cfg['candlestick_confirmation_enabled']:
            confirming_pattern = self._get_candlestick_confirmation(signal_direction, min_reliability='Medium')
            if not confirming_pattern:
                return None
            confirmations['candlestick_filter'] = f"Passed (Pattern: {confirming_pattern.get('name')})"

        # --- 4. Risk Management & Final Checks (Logic is 100% preserved) ---
        entry_price = self.price_data.get('close')
        if not entry_price: return None
        
        stop_loss = keltner_data.get('values', {}).get('middle_band')
        if not stop_loss: return None
            
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        
        if not risk_params or risk_params.get("risk_reward_ratio", 0) < cfg['min_rr_ratio']:
            return None
        confirmations['rr_check'] = f"Passed (R/R: {risk_params.get('risk_reward_ratio')})"
        
        logger.info(f"✨✨ [{self.strategy_name}] KELTNER MOMENTUM SIGNAL CONFIRMED! ✨✨")

        # --- 5. Package and Return the Legendary Signal ---
        return {
            "direction": signal_direction,
            "entry_price": entry_price,
            **risk_params,
            "confirmations": confirmations
        }
