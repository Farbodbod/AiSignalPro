import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class VwapReversionPro(BaseStrategy):
    """
    VwapReversionPro - The Legendary, Unrivaled, World-Class Version
    ------------------------------------------------------------------
    This is a high-precision, intraday mean-reversion strategy. It operates
    on the principle that prices that deviate significantly from the session's
    VWAP are likely to revert.

    The Funnel:
    1.  Trigger: Price must close outside the VWAP's standard deviation bands.
    2.  Filter 1 (Dual Oscillator): Confirm momentum exhaustion with simultaneous
        Overbought/Oversold signals from both RSI and Williams %R.
    3.  Filter 2 (Price Action): A confirming candlestick reversal pattern must appear.
    4.  Risk Management: SL is placed logically outside the VWAP band using ATR.
    5.  Smart Targeting: The primary target is the VWAP line itself.
    """
    strategy_name: str = "VwapReversionPro"

    def _get_signal_config(self) -> Dict[str, Any]:
        """Loads and validates the strategy's specific parameters from the config."""
        return {
            # Note: The VWAP reset_period should be configured in the indicators config
            "rsi_oversold": float(self.config.get("rsi_oversold", 30.0)),
            "rsi_overbought": float(self.config.get("rsi_overbought", 70.0)),
            "williams_r_oversold": float(self.config.get("williams_r_oversold", -80.0)),
            "williams_r_overbought": float(self.config.get("williams_r_overbought", -20.0)),
            "atr_sl_multiplier": float(self.config.get("atr_sl_multiplier", 1.5)),
            "min_rr_ratio": float(self.config.get("min_risk_reward_ratio", 1.0)),
            "require_candle_confirmation": bool(self.config.get("require_candle_confirmation", True)),
        }

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self._get_signal_config()
        
        # --- 1. Get Required Data using the Toolkit ---
        vwap_data = self.get_indicator('vwap_bands')
        rsi_data = self.get_indicator('rsi')
        wr_data = self.get_indicator('williams_r')
        atr_data = self.get_indicator('atr')

        if not all([vwap_data, rsi_data, wr_data, atr_data, self.price_data]):
            return None

        # --- 2. Primary Trigger: Price Extension beyond VWAP Bands ---
        vwap_analysis = vwap_data.get('analysis', {})
        vwap_position = vwap_analysis.get('position')
        
        signal_direction = None
        if "Overextended Below" in vwap_position: signal_direction = "BUY"
        elif "Overextended Above" in vwap_position: signal_direction = "SELL"
        else: return None
        
        logger.info(f"[{self.strategy_name}] Initial Trigger: Price is overextended {signal_direction} from VWAP.")
        confirmations = {"trigger": f"Price {vwap_position}"}

        # --- 3. Confirmation Funnel ---
        # Filter 1: Dual Oscillator Confirmation
        rsi_value = rsi_data.get('values', {}).get('rsi', 50)
        wr_value = wr_data.get('values', {}).get('wr', -50)

        osc_confirmed = False
        if signal_direction == "BUY" and rsi_value < cfg['rsi_oversold'] and wr_value < cfg['williams_r_oversold']:
            osc_confirmed = True
        elif signal_direction == "SELL" and rsi_value > cfg['rsi_overbought'] and wr_value > cfg['williams_r_overbought']:
            osc_confirmed = True

        if not osc_confirmed:
            logger.info(f"[{self.strategy_name}] Signal REJECTED: Lack of dual oscillator confirmation (RSI: {rsi_value:.2f}, W%R: {wr_value:.2f}).")
            return None
        confirmations['oscillator_filter'] = "Passed (RSI & W%R agree)"

        # Filter 2: Candlestick Confirmation (Optional)
        if cfg['require_candle_confirmation']:
            confirming_pattern = self._get_candlestick_confirmation(signal_direction, min_reliability='Medium')
            if not confirming_pattern:
                logger.info(f"[{self.strategy_name}] Signal REJECTED: No confirming candlestick pattern.")
                return None
            confirmations['candlestick_filter'] = f"Passed (Pattern: {confirming_pattern.get('name')})"

        # --- 4. Risk Management & Final Checks ---
        entry_price = self.price_data.get('close')
        atr_value = atr_data.get('values', {}).get('atr')
        vwap_values = vwap_data.get('values', {})
        if not all([entry_price, atr_value, vwap_values]): return None
        
        # Stop loss is placed logically outside the VWAP band, cushioned by ATR
        stop_loss = 0
        if signal_direction == "BUY":
            lower_band = vwap_values.get('lower_band')
            if not lower_band: return None
            stop_loss = lower_band - (atr_value * cfg['atr_sl_multiplier'])
        else: # SELL
            upper_band = vwap_values.get('upper_band')
            if not upper_band: return None
            stop_loss = upper_band + (atr_value * cfg['atr_sl_multiplier'])
        
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        
        # Smart Targeting: The primary target for mean reversion is the VWAP line itself.
        vwap_line = vwap_values.get('vwap')
        if vwap_line and risk_params.get('targets'):
            risk_params['targets'][0] = vwap_line
            # Recalculate R/R based on this primary, high-probability target
            risk_amount = abs(entry_price - stop_loss)
            if risk_amount > 1e-9:
                risk_params['risk_reward_ratio'] = round(abs(vwap_line - entry_price) / risk_amount, 2)
        
        # Pre-Trade R/R Check
        if not risk_params or risk_params.get("risk_reward_ratio", 0) < cfg['min_rr_ratio']:
            rr_ratio = risk_params.get("risk_reward_ratio", 0)
            logger.info(f"[{self.strategy_name}] Signal REJECTED: Initial R/R ratio ({rr_ratio}) to VWAP is below threshold ({cfg['min_rr_ratio']}).")
            return None
        confirmations['rr_check'] = f"Passed (R/R to VWAP: {risk_params.get('risk_reward_ratio')})"
        
        logger.info(f"✨✨ [{self.strategy_name}] VWAP REVERSION SNIPER SIGNAL CONFIRMED! ✨✨")

        # --- 5. Package and Return the Legendary Signal ---
        return {
            "direction": signal_direction,
            "entry_price": entry_price,
            **risk_params,
            "confirmations": confirmations
        }
