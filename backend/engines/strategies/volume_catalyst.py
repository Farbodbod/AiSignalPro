import logging
from typing import Dict, Any, Optional, Tuple
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class VolumeCatalystPro(BaseStrategy):
    """
    VolumeCatalystPro - The Anti-Fragile, World-Class Version
    This version is hardened against data failures by using the safe `get_indicator`
    method from its parent, ensuring it exits gracefully if any required data is missing.
    """
    strategy_name: str = "VolumeCatalystPro"

    def _get_signal_config(self) -> Dict[str, Any]:
        return {
            "cci_threshold": float(self.config.get("cci_threshold", 100.0)),
            "min_rr_ratio": float(self.config.get("min_risk_reward_ratio", 1.5)),
            "htf_confirmation_enabled": bool(self.config.get("htf_confirmation_enabled", True)),
        }

    def _find_structural_breakout(self) -> Optional[Tuple[str, float]]:
        # ✅ FIX: Use the safe getter
        structure_data = self.get_indicator('structure')
        if not structure_data: return None, None
        
        # We need the full DataFrame, which must be passed in the analysis package
        if self.df is None or len(self.df) < 2: return None, None
        
        prev_close = self.df['close'].iloc[-2]
        current_price = self.price_data.get('close')
        
        nearest_resistance = structure_data['analysis']['proximity'].get('nearest_resistance')
        if nearest_resistance and prev_close <= nearest_resistance < current_price:
            return "BUY", nearest_resistance

        nearest_support = structure_data['analysis']['proximity'].get('nearest_support')
        if nearest_support and prev_close >= nearest_support > current_price:
            return "SELL", nearest_support
            
        return None, None

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self._get_signal_config()
        
        # ✅ FIX: Check the validity of required indicators at the beginning
        # This makes the strategy anti-fragile.
        whales_data = self.get_indicator('whales')
        cci_data = self.get_indicator('cci')
        keltner_data = self.get_indicator('keltner_channel')
        
        if not all([whales_data, cci_data, keltner_data]):
            logger.debug(f"[{self.strategy_name}] Signal check skipped: Missing one or more required indicators (whales, cci, keltner).")
            return None

        # --- 1. Primary Trigger: Find a Structural Breakout ---
        signal_direction, broken_level = self._find_structural_breakout()
        if not signal_direction: return None
        
        logger.info(f"[{self.strategy_name}] Initial Trigger: {signal_direction} breakout of structure level {broken_level:.5f}.")
        confirmations = {"trigger": f"Breakout of S/R Level at {broken_level:.5f}"}

        # --- 2. The Catalyst: Volume Confirmation ---
        if not whales_data.get('analysis', {}).get('is_whale_activity'):
            return None
        
        whale_pressure = whales_data['analysis'].get('pressure', '')
        if (signal_direction == "BUY" and "Buying" not in whale_pressure) or \
           (signal_direction == "SELL" and "Selling" not in whale_pressure):
            return None
        confirmations['volume_catalyst'] = f"Passed (Spike Score: {whales_data['analysis'].get('spike_score', 'N/A')})"

        # --- 3. Confirmation Funnel ---
        cci_value = cci_data.get('values', {}).get('value', 0)
        if (signal_direction == "BUY" and cci_value < cfg['cci_threshold']) or \
           (signal_direction == "SELL" and cci_value > -cfg['cci_threshold']):
            return None
        confirmations['momentum_filter'] = f"Passed (CCI: {cci_value:.2f})"

        if keltner_data.get('analysis', {}).get('is_in_squeeze', True):
            return None
        confirmations['volatility_filter'] = "Passed (Exiting Squeeze)"

        if cfg['htf_confirmation_enabled']:
            htf_timeframe = self.config.get("htf_timeframe", "4h")
            if not self._get_trend_confirmation(signal_direction, htf_timeframe):
                return None
            confirmations['htf_filter'] = f"Passed (Aligned with {htf_timeframe})"
        
        # --- 4. Risk Management & Final Checks ---
        entry_price = self.price_data.get('close')
        stop_loss = keltner_data.get('values', {}).get('middle_band')
        if not entry_price or not stop_loss: return None
            
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        
        if not risk_params or risk_params.get("risk_reward_ratio", 0) < cfg['min_rr_ratio']:
            return None
        confirmations['rr_check'] = f"Passed (R/R: {risk_params.get('risk_reward_ratio', 0):.2f})"
        
        logger.info(f"✨✨ [{self.strategy_name}] VOLUME CATALYST SIGNAL CONFIRMED! ✨✨")

        return {
            "direction": signal_direction, "entry_price": entry_price,
            **risk_params, "confirmations": confirmations
        }
