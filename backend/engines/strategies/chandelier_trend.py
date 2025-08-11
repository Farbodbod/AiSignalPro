import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class ChandelierTrendRider(BaseStrategy):
    """
    ChandelierTrendRider - (v2.0 - Anti-Fragile Edition)
    -------------------------------------------------------------------------
    This version is hardened against data failures. It fetches all required
    indicator data upfront and verifies its integrity before executing the
    core trading logic, making it robust and reliable.
    """
    strategy_name: str = "ChandelierTrendRider"

    def _get_signal_config(self) -> Dict[str, Any]:
        """Loads and validates the strategy's specific parameters from the config."""
        return {
            "min_adx_strength": float(self.config.get("min_adx_strength", 25.0)),
            "min_rr_ratio": float(self.config.get("min_risk_reward_ratio", 1.2)),
            "htf_confirmation_enabled": bool(self.config.get("htf_confirmation_enabled", True)),
            "htf_timeframe": str(self.config.get("htf_timeframe", "4h")),
            "volume_confirmation_enabled": bool(self.config.get("volume_confirmation_enabled", False)),
            "candlestick_confirmation_enabled": bool(self.config.get("candlestick_confirmation_enabled", False)),
        }

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self._get_signal_config()
        
        # --- ✅ 1. Anti-Fragile Data Check ---
        if not self.price_data:
            return None

        # Safely get all required indicator data.
        supertrend_data = self.get_indicator('supertrend')
        adx_data = self.get_indicator('adx')
        chandelier_data = self.get_indicator('chandelier_exit')
        
        # The core logic requires these three. If any fails, exit gracefully.
        if not all([supertrend_data, adx_data, chandelier_data]):
            logger.debug(f"[{self.strategy_name}] Skipped: Missing one or more required indicators.")
            return None

        # --- 2. Get Primary Signal from SuperTrend Crossover ---
        st_signal = supertrend_data.get('analysis', {}).get('signal')
        signal_direction = None
        if st_signal == "Bullish Crossover": signal_direction = "BUY"
        elif st_signal == "Bearish Crossover": signal_direction = "SELL"
        else: return None
        
        logger.info(f"[{self.strategy_name}] Initial Signal: {signal_direction} from SuperTrend.")
        confirmations = {"entry_trigger": "SuperTrend Crossover"}

        # --- 3. Confirmation Funnel (Logic is 100% preserved) ---
        adx_strength = adx_data.get('values', {}).get('adx', 0)
        if adx_strength < cfg['min_adx_strength']:
            return None
        confirmations['adx_filter'] = f"Passed (ADX: {adx_strength:.2f})"

        if cfg['htf_confirmation_enabled']:
            if not self._get_trend_confirmation(signal_direction, cfg['htf_timeframe']):
                return None
            confirmations['htf_filter'] = f"Passed (Aligned with {cfg['htf_timeframe']})"

        if cfg['volume_confirmation_enabled']:
            if not self._get_volume_confirmation():
                return None
            confirmations['volume_filter'] = "Passed (Whale activity detected)"

        if cfg['candlestick_confirmation_enabled']:
            confirming_pattern = self._get_candlestick_confirmation(signal_direction)
            if not confirming_pattern:
                return None
            confirmations['candlestick_filter'] = f"Passed (Pattern: {confirming_pattern.get('name')})"

        # --- 4. Calculate Risk & Perform Pre-Trade R/R Check (Logic is 100% preserved) ---
        entry_price = self.price_data.get('close')
        if not entry_price: return None
        
        stop_loss_key = 'long_stop' if signal_direction == "BUY" else 'short_stop'
        stop_loss = chandelier_data.get('values', {}).get(stop_loss_key)
        if not stop_loss: return None
            
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        
        if not risk_params or risk_params.get("risk_reward_ratio", 0) < cfg['min_rr_ratio']:
            return None
        confirmations['rr_check'] = f"Passed (R/R: {risk_params.get('risk_reward_ratio')})"

        logger.info(f"✨✨ [{self.strategy_name}] TREND RIDER SIGNAL CONFIRMED! ✨✨")
        
        # --- 5. Package and Return the Final Signal ---
        return {
            "direction": signal_direction,
            "entry_price": entry_price,
            **risk_params,
            "confirmations": confirmations
        }
