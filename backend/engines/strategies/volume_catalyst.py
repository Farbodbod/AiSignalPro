import logging
from typing import Dict, Any, Optional, Tuple
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class VolumeCatalystPro(BaseStrategy):
    """
    VolumeCatalystPro - The Legendary, Unrivaled, World-Class Version
    ------------------------------------------------------------------
    This is an advanced breakout strategy that operates on the philosophy of
    "smart money catalysis". It ignores simple price breakouts and hunts for
    structural breaks that are catalyzed by a significant volume spike (whale activity)
    and confirmed by momentum (CCI) and volatility expansion (Keltner).

    The Funnel:
    1.  Trigger: A clean breakout of a key structural support/resistance level.
    2.  Catalyst: The breakout candle must be confirmed by the WhaleIndicator.
    3.  Filter 1 (Momentum): CCI must confirm strong momentum in the breakout direction.
    4.  Filter 2 (Volatility): Keltner Channels must show volatility expansion.
    5.  Final Checks: Optional HTF alignment and a pre-trade R/R check.
    """
    strategy_name: str = "VolumeCatalystPro"

    def _get_signal_config(self) -> Dict[str, Any]:
        """Loads and validates the strategy's specific parameters from the config."""
        return {
            "cci_threshold": float(self.config.get("cci_threshold", 100.0)),
            "min_rr_ratio": float(self.config.get("min_risk_reward_ratio", 1.5)),
            "htf_confirmation_enabled": bool(self.config.get("htf_confirmation_enabled", True)),
            "htf_timeframe": str(self.config.get("htf_timeframe", "4h")),
        }

    def _find_structural_breakout(self) -> Optional[Tuple[str, float]]:
        """
        Finds the first clean breakout of the nearest key support or resistance level.
        Returns: (direction, broken_level_price) or (None, None)
        """
        structure_data = self.get_indicator('structure')
        if not structure_data or 'analysis' not in structure_data: return None, None
        
        # We need the previous candle's close to confirm a break occurred on the current candle
        if len(self.df) < 2: return None, None
        prev_close = self.df['close'].iloc[-2]
        current_price = self.price_data.get('close')
        
        # Check for resistance break (BUY signal)
        nearest_resistance = structure_data['analysis']['proximity'].get('nearest_resistance')
        if nearest_resistance and prev_close <= nearest_resistance < current_price:
            return "BUY", nearest_resistance

        # Check for support break (SELL signal)
        nearest_support = structure_data['analysis']['proximity'].get('nearest_support')
        if nearest_support and prev_close >= nearest_support > current_price:
            return "SELL", nearest_support
            
        return None, None

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self._get_signal_config()

        # --- 1. Primary Trigger: Find a Structural Breakout ---
        signal_direction, broken_level = self._find_structural_breakout()
        if not signal_direction: return None
        
        logger.info(f"[{self.strategy_name}] Initial Trigger: {signal_direction} breakout of structure level {broken_level:.5f}.")
        confirmations = {"trigger": f"Breakout of S/R Level at {broken_level:.5f}"}

        # --- 2. The Catalyst: Volume Confirmation ---
        whales_data = self.get_indicator('whales')
        if not whales_data or not whales_data.get('analysis', {}).get('is_whale_activity'):
            logger.info(f"[{self.strategy_name}] Signal REJECTED: Breakout lacks the volume catalyst.")
            return None
        
        # Check if the whale pressure aligns with the breakout direction
        whale_pressure = whales_data['analysis'].get('pressure')
        if (signal_direction == "BUY" and "Buying" not in whale_pressure) or \
           (signal_direction == "SELL" and "Selling" not in whale_pressure):
            logger.info(f"[{self.strategy_name}] Signal REJECTED: Whale pressure does not align with breakout direction.")
            return None
        confirmations['volume_catalyst'] = f"Passed (Spike Score: {whales_data['analysis']['spike_score']})"

        # --- 3. Confirmation Funnel ---
        # Filter 1: CCI Momentum Confirmation
        cci_data = self.get_indicator('cci')
        if not cci_data or cci_data.get('status') != 'OK': return None
        cci_value = cci_data.get('values', {}).get('value', 0)
        
        if (signal_direction == "BUY" and cci_value < cfg['cci_threshold']) or \
           (signal_direction == "SELL" and cci_value > -cfg['cci_threshold']):
            logger.info(f"[{self.strategy_name}] Signal REJECTED: CCI momentum ({cci_value:.2f}) is not confirming.")
            return None
        confirmations['momentum_filter'] = f"Passed (CCI: {cci_value:.2f})"

        # Filter 2: Volatility Expansion Confirmation
        keltner_data = self.get_indicator('keltner_channel')
        if not keltner_data or not keltner_data.get('analysis', {}).get('is_in_squeeze') is False:
            logger.info(f"[{self.strategy_name}] Signal REJECTED: No volatility expansion (still in squeeze).")
            return None
        confirmations['volatility_filter'] = "Passed (Exiting Squeeze)"

        # Filter 3: Higher-Timeframe Trend Confirmation (Optional)
        if cfg['htf_confirmation_enabled']:
            if not self._get_trend_confirmation(signal_direction, cfg['htf_timeframe']):
                logger.info(f"[{self.strategy_name}] Signal REJECTED: Breakout is against the {cfg['htf_timeframe']} trend.")
                return None
            confirmations['htf_filter'] = f"Passed (Aligned with {cfg['htf_timeframe']})"
        
        # --- 4. Risk Management & Final Checks ---
        entry_price = self.price_data.get('close')
        if not entry_price: return None
        
        # Stop loss is placed on the Keltner Channel's middle line, a dynamic level.
        stop_loss = keltner_data.get('values', {}).get('middle_band')
        if not stop_loss: return None
            
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        
        if not risk_params or risk_params.get("risk_reward_ratio", 0) < cfg['min_rr_ratio']:
            logger.info(f"[{self.strategy_name}] Signal REJECTED: Initial R/R ratio is below threshold.")
            return None
        confirmations['rr_check'] = f"Passed (R/R: {risk_params.get('risk_reward_ratio')})"
        
        logger.info(f"✨✨ [{self.strategy_name}] VOLUME CATALYST SIGNAL CONFIRMED! ✨✨")

        # --- 5. Package and Return the Legendary Signal ---
        return {
            "direction": signal_direction,
            "entry_price": entry_price,
            **risk_params,
            "confirmations": confirmations
        }
