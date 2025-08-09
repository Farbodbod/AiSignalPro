import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class VwapMeanReversion(BaseStrategy):
    """
    VwapMeanReversion - The Legendary, Unrivaled, World-Class Meta-Strategy
    -------------------------------------------------------------------------
    This is not a single strategy but a highly flexible framework for executing
    mean-reversion trades around the VWAP. By adjusting its configuration, it can
    act as a conservative "Bouncer" or an aggressive "ReversionPro".

    The Funnel:
    1.  Trigger: Price tests or breaks the VWAP standard deviation bands.
    2.  Filter 1 (Oscillator Engine): Confirms momentum exhaustion using a
        configurable combination of RSI and/or Williams %R.
    3.  Filter 2 (Price Action): A confirming candlestick reversal pattern appears.
    4.  Risk Management: SL is placed logically outside the VWAP band, cushioned by ATR.
    5.  Smart Targeting: The primary target is always the VWAP line itself.
    """
    strategy_name: str = "VwapMeanReversion"

    def _get_signal_config(self) -> Dict[str, Any]:
        """Loads and validates the strategy's specific parameters from the config."""
        return {
            # VWAP reset period (e.g., 'D') is configured in the indicator's config
            "vwap_std_dev_multiplier": float(self.config.get("vwap_std_dev_multiplier", 2.0)),
            # --- Oscillator Confirmation Engine ---
            "oscillator_logic": str(self.config.get("oscillator_logic", "AND")).upper(), # "AND", "OR"
            "use_rsi": bool(self.config.get("use_rsi", True)),
            "rsi_oversold": float(self.config.get("rsi_oversold", 30.0)),
            "rsi_overbought": float(self.config.get("rsi_overbought", 70.0)),
            "use_williams_r": bool(self.config.get("use_williams_r", True)),
            "williams_r_oversold": float(self.config.get("williams_r_oversold", -80.0)),
            "williams_r_overbought": float(self.config.get("williams_r_overbought", -20.0)),
            # --- Risk and Confirmation ---
            "atr_sl_multiplier": float(self.config.get("atr_sl_multiplier", 1.5)),
            "min_rr_ratio": float(self.config.get("min_risk_reward_ratio", 1.0)),
            "require_candle_confirmation": bool(self.config.get("require_candle_confirmation", True)),
        }

    def _get_oscillator_confirmation(self, direction: str, cfg: Dict[str, Any]) -> bool:
        """The heart of the strategy: the Oscillator Confirmation Engine."""
        rsi_data = self.get_indicator('rsi'); wr_data = self.get_indicator('williams_r')
        
        rsi_confirm = False
        if cfg['use_rsi'] and rsi_data:
            rsi_val = rsi_data.get('values', {}).get('rsi')
            if rsi_val is not None:
                if direction == "BUY" and rsi_val < cfg['rsi_oversold']: rsi_confirm = True
                elif direction == "SELL" and rsi_val > cfg['rsi_overbought']: rsi_confirm = True

        wr_confirm = False
        if cfg['use_williams_r'] and wr_data:
            wr_val = wr_data.get('values', {}).get('wr')
            if wr_val is not None:
                if direction == "BUY" and wr_val < cfg['williams_r_oversold']: wr_confirm = True
                elif direction == "SELL" and wr_val > cfg['williams_r_overbought']: wr_confirm = True
        
        if cfg['oscillator_logic'] == "AND":
            return rsi_confirm and wr_confirm
        elif cfg['oscillator_logic'] == "OR":
            return rsi_confirm or wr_confirm
        
        return False

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self._get_signal_config()
        
        # --- 1. Get Required Data & Primary Trigger ---
        vwap_data = self.get_indicator('vwap_bands')
        if not vwap_data or vwap_data.get('status') != 'OK': return None

        vwap_analysis = vwap_data.get('analysis', {}); vwap_position = vwap_analysis.get('position')
        
        signal_direction = None
        if "Below" in vwap_position: signal_direction = "BUY"
        elif "Above" in vwap_position: signal_direction = "SELL"
        else: return None
        
        logger.info(f"[{self.strategy_name}] Initial Trigger: Price is overextended {signal_direction} from VWAP.")
        confirmations = {"trigger": f"Price {vwap_position}"}

        # --- 2. Confirmation Funnel ---
        # Filter 1: Oscillator Confirmation Engine
        if not self._get_oscillator_confirmation(signal_direction, cfg):
            logger.info(f"[{self.strategy_name}] Signal REJECTED: Lack of oscillator confirmation.")
            return None
        confirmations['oscillator_filter'] = f"Passed (Logic: {cfg['oscillator_logic']})"

        # Filter 2: Candlestick Confirmation (Optional)
        if cfg['require_candle_confirmation']:
            confirming_pattern = self._get_candlestick_confirmation(signal_direction, min_reliability='Medium')
            if not confirming_pattern:
                logger.info(f"[{self.strategy_name}] Signal REJECTED: No confirming candlestick pattern.")
                return None
            confirmations['candlestick_filter'] = f"Passed (Pattern: {confirming_pattern.get('name')})"

        # --- 3. Risk Management & Final Checks ---
        entry_price = self.price_data.get('close')
        atr_data = self.get_indicator('atr')
        vwap_values = vwap_data.get('values', {})
        if not all([entry_price, atr_data, vwap_values]): return None
        
        atr_value = atr_data.get('values', {}).get('atr', entry_price * 0.01)
        
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
        
        # Smart Targeting: The primary target for mean reversion is the VWAP line.
        vwap_line = vwap_values.get('vwap')
        if vwap_line and risk_params.get('targets'):
            risk_params['targets'][0] = vwap_line
            risk_amount = abs(entry_price - stop_loss)
            if risk_amount > 1e-9:
                risk_params['risk_reward_ratio'] = round(abs(vwap_line - entry_price) / risk_amount, 2)
        
        # Pre-Trade R/R Check
        if not risk_params or risk_params.get("risk_reward_ratio", 0) < cfg['min_rr_ratio']:
            logger.info(f"[{self.strategy_name}] Signal REJECTED: Initial R/R ratio to VWAP is below threshold.")
            return None
        confirmations['rr_check'] = f"Passed (R/R to VWAP: {risk_params.get('risk_reward_ratio')})"
        
        logger.info(f"✨✨ [{self.strategy_name}] VWAP MEAN REVERSION SIGNAL CONFIRMED! ✨✨")

        # --- 4. Package and Return the Legendary Signal ---
        return { "direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations }
