import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class KeltnerMomentumBreakout(BaseStrategy):
    """
    KeltnerMomentumBreakout - The Legendary, Unrivaled, World-Class Version
    -------------------------------------------------------------------------
    This is a professional-grade momentum breakout strategy. It identifies breakouts
    from a volatility channel (Keltner) and validates them with a powerful
    dual-filter system of trend strength (ADX) and momentum (CCI).

    The Funnel:
    1.  Signal: A clean price breakout of the Keltner Channel.
    2.  Filter 1 (Trend Strength): ADX must indicate a trending market.
    3.  Filter 2 (Momentum): CCI must confirm strong momentum in the breakout direction.
    4.  Filter 3 (Optional - Price Action): A confirming candlestick pattern.
    5.  Filter 4 (Optional - HTF): The breakout aligns with the higher-timeframe trend.
    6.  Risk Management: A pre-trade R/R check is performed with a dynamic SL on the EMA.
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
        
        # --- 1. Get Primary Signal from Keltner Channel Breakout ---
        keltner_data = self.get_indicator('keltner_channel')
        if not keltner_data or keltner_data.get('status') != 'OK': return None

        keltner_pos = keltner_data.get('analysis', {}).get('position')
        signal_direction = None
        if "Breakout Above" in keltner_pos: signal_direction = "BUY"
        elif "Breakdown Below" in keltner_pos: signal_direction = "SELL"
        else: return None
        
        logger.info(f"[{self.strategy_name}] Initial Signal: {signal_direction} from Keltner Channel breakout.")
        confirmations = {"entry_trigger": "Keltner Channel Breakout"}

        # --- 2. Confirmation Funnel ---
        # Filter 1: ADX Trend Strength
        adx_data = self.get_indicator('adx')
        if not adx_data or adx_data.get('status') != 'OK': return None
        adx_strength = adx_data.get('values', {}).get('adx', 0)
        if adx_strength < cfg['min_adx_strength']:
            logger.info(f"[{self.strategy_name}] Signal REJECTED: ADX strength ({adx_strength:.2f}) is below threshold.")
            return None
        confirmations['adx_filter'] = f"Passed (ADX: {adx_strength:.2f})"

        # Filter 2: CCI Momentum Confirmation
        cci_data = self.get_indicator('cci')
        if not cci_data or cci_data.get('status') != 'OK': return None
        cci_value = cci_data.get('values', {}).get('value', 0)
        
        cci_confirmed = False
        if signal_direction == "BUY" and cci_value > cfg['cci_threshold']:
            cci_confirmed = True
        elif signal_direction == "SELL" and cci_value < -cfg['cci_threshold']:
            cci_confirmed = True
            
        if not cci_confirmed:
            logger.info(f"[{self.strategy_name}] Signal REJECTED: CCI momentum ({cci_value:.2f}) is not confirming.")
            return None
        confirmations['cci_filter'] = f"Passed (CCI: {cci_value:.2f})"

        # Filter 3: Higher-Timeframe Trend Confirmation (Optional)
        if cfg['htf_confirmation_enabled']:
            if not self._get_trend_confirmation(signal_direction, cfg['htf_timeframe']):
                logger.info(f"[{self.strategy_name}] Signal REJECTED: Not aligned with {cfg['htf_timeframe']} trend.")
                return None
            confirmations['htf_filter'] = f"Passed (Aligned with {cfg['htf_timeframe']})"
        
        # Filter 4: Candlestick Confirmation (Optional)
        if cfg['candlestick_confirmation_enabled']:
            confirming_pattern = self._get_candlestick_confirmation(signal_direction, min_reliability='Medium')
            if not confirming_pattern:
                logger.info(f"[{self.strategy_name}] Signal REJECTED: No confirming candlestick pattern.")
                return None
            confirmations['candlestick_filter'] = f"Passed (Pattern: {confirming_pattern.get('name')})"

        # --- 3. Risk Management & Final Checks ---
        entry_price = self.price_data.get('close')
        if not entry_price: return None
        
        # Stop loss is placed on the Keltner Channel's middle line (EMA), a key dynamic level.
        stop_loss = keltner_data.get('values', {}).get('middle_band')
        if not stop_loss: return None
            
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        
        # Pre-Trade R/R Check
        if not risk_params or risk_params.get("risk_reward_ratio", 0) < cfg['min_rr_ratio']:
            rr_ratio = risk_params.get("risk_reward_ratio", 0)
            logger.info(f"[{self.strategy_name}] Signal REJECTED: Initial R/R ratio ({rr_ratio}) is below threshold ({cfg['min_rr_ratio']}).")
            return None
        confirmations['rr_check'] = f"Passed (R/R: {risk_params.get('risk_reward_ratio')})"
        
        logger.info(f"✨✨ [{self.strategy_name}] KELTNER MOMENTUM SIGNAL CONFIRMED! ✨✨")

        # --- 4. Package and Return the Legendary Signal ---
        return {
            "direction": signal_direction,
            "entry_price": entry_price,
            **risk_params,
            "confirmations": confirmations
        }
