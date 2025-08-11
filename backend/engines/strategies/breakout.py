import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class BreakoutHunter(BaseStrategy):
    """
    BreakoutHunter - (v2.0 - Anti-Fragile Edition)
    ----------------------------------------------------------------
    This version is hardened against data failures. It fetches all required
    indicator data upfront and verifies its integrity before executing the
    core trading logic, making it robust and reliable.
    """
    strategy_name: str = "BreakoutHunter"

    def _get_signal_config(self) -> Dict[str, Any]:
        """Loads and validates the strategy's specific parameters from the config."""
        return {
            "volatility_indicator": str(self.config.get("volatility_indicator", "keltner_channel")),
            "min_rr_ratio": float(self.config.get("min_risk_reward_ratio", 1.5)),
            "htf_confirmation_enabled": bool(self.config.get("htf_confirmation_enabled", True)),
            "htf_timeframe": str(self.config.get("htf_timeframe", "4h")),
        }

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self._get_signal_config()
        
        # --- ✅ 1. Anti-Fragile Data Check ---
        if not self.price_data:
            return None
            
        # Safely get all required indicator data.
        volatility_indicator_name = cfg['volatility_indicator']
        volatility_data = self.get_indicator(volatility_indicator_name)
        donchian_data = self.get_indicator('donchian_channel')
        whales_data = self.get_indicator('whales') # Needed for volume confirmation
        
        # The core logic requires these three. If any fails, exit gracefully.
        if not all([volatility_data, donchian_data, whales_data]):
            logger.debug(f"[{self.strategy_name}] Skipped: Missing one or more required indicators.")
            return None

        # --- 2. Pre-condition: Check for a Volatility Squeeze ---
        is_in_squeeze = volatility_data['analysis'].get('is_in_squeeze', False)

        # --- 3. Primary Signal: Donchian Channel Breakout ---
        donchian_signal = donchian_data.get('analysis', {}).get('signal')
        signal_direction = None
        if donchian_signal == "Buy": signal_direction = "BUY"
        elif donchian_signal == "Sell": signal_direction = "SELL"
        else: return None
        
        logger.info(f"[{self.strategy_name}] Initial Signal: {signal_direction} from Donchian breakout.")
        confirmations = {"entry_trigger": "Donchian Channel Breakout"}
        
        # --- 4. Confirmation Funnel (Logic is 100% preserved) ---
        if not self._get_volume_confirmation():
            return None
        confirmations['volume_filter'] = "Passed (Whale activity detected)"
        
        if is_in_squeeze:
             return None
        confirmations['volatility_filter'] = "Passed (Volatility Expansion)"

        if cfg['htf_confirmation_enabled']:
            if not self._get_trend_confirmation(signal_direction, cfg['htf_timeframe']):
                return None
            confirmations['htf_filter'] = f"Passed (Aligned with {cfg['htf_timeframe']})"

        # --- 5. Risk Management & Final Checks (Logic is 100% preserved) ---
        entry_price = self.price_data.get('close')
        if not entry_price: return None
        
        stop_loss = donchian_data.get('values', {}).get('middle_band')
        if not stop_loss: return None
            
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        
        if not risk_params or risk_params.get("risk_reward_ratio", 0) < cfg['min_rr_ratio']:
            return None
        confirmations['rr_check'] = f"Passed (R/R: {risk_params.get('risk_reward_ratio')})"
        
        logger.info(f"✨✨ [{self.strategy_name}] BREAKOUT HUNTER SIGNAL CONFIRMED! ✨✨")

        # --- 6. Package and Return the Legendary Signal ---
        return {
            "direction": signal_direction,
            "entry_price": entry_price,
            **risk_params,
            "confirmations": confirmations
        }
