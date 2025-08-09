import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class EmaCrossoverStrategy(BaseStrategy):
    """
    EmaCrossoverPro - Definitive, Toolkit-Powered, World-Class Version
    -------------------------------------------------------------------
    This strategy identifies EMA crossovers and validates them through a
    rigorous, multi-layered filtering process using the BaseStrategy toolkit.
    1.  Primary Signal: EMA Crossover.
    2.  Filter 1: ADX for trend strength.
    3.  Filter 2: Higher-Timeframe trend alignment.
    4.  Filter 3: Candlestick pattern confirmation.
    5.  Risk Management: ATR-based Stop Loss from the long-term EMA.
    """
    strategy_name: str = "EmaCrossoverPro"

    def _get_signal_config(self) -> Dict[str, Any]:
        """Loads and validates the strategy's specific parameters from the config."""
        return {
            "short_period": int(self.config.get("short_period", 9)),
            "long_period": int(self.config.get("long_period", 21)),
            "min_adx_strength": float(self.config.get("min_adx_strength", 23.0)),
            "atr_period_for_sl": int(self.config.get("atr_period_for_sl", 14)),
            "atr_sl_multiplier": float(self.config.get("atr_sl_multiplier", 2.5)),
            "htf_confirmation_enabled": bool(self.config.get("htf_confirmation_enabled", True)),
            "htf_timeframe": str(self.config.get("htf_timeframe", "4h")),
            "candlestick_confirmation_enabled": bool(self.config.get("candlestick_confirmation_enabled", True)),
        }

    def check_signal(self) -> Optional[Dict[str, Any]]:
        """
        Executes the multi-layered filtering logic to find a high-probability signal.
        The code reads like a trading plan thanks to the BaseStrategy toolkit.
        """
        cfg = self._get_signal_config()
        
        # --- 1. Get Primary Signal ---
        ema_cross_data = self.get_indicator('ema_cross')
        if not ema_cross_data or ema_cross_data.get('status') != 'OK': return None

        primary_signal = ema_cross_data.get('analysis', {}).get('signal')
        if primary_signal not in ["Buy", "Sell"]:
            return None
        
        signal_direction = primary_signal.upper()
        logger.info(f"[{self.strategy_name}] Initial Signal: {signal_direction} EMA Crossover found.")
        
        # --- 2. Apply Confirmation Filters ---
        confirmations = {"entry_trigger": f"EMA Cross ({cfg['short_period']}/{cfg['long_period']})"}

        # Filter 1: ADX Trend Strength
        adx_data = self.get_indicator('adx')
        if not adx_data or adx_data.get('status') != 'OK': return None
        adx_strength = adx_data.get('values', {}).get('adx', 0)
        if adx_strength < cfg['min_adx_strength']:
            logger.info(f"[{self.strategy_name}] Signal REJECTED: ADX strength ({adx_strength:.2f}) is below threshold ({cfg['min_adx_strength']}).")
            return None
        confirmations['adx_filter'] = f"Passed (ADX: {adx_strength:.2f})"
        
        # Filter 2: Higher-Timeframe Trend Confirmation (Optional)
        if cfg['htf_confirmation_enabled']:
            if not self._get_trend_confirmation(signal_direction, cfg['htf_timeframe']):
                logger.info(f"[{self.strategy_name}] Signal REJECTED: Trend confirmation failed on {cfg['htf_timeframe']}.")
                return None
            confirmations['htf_filter'] = f"Passed (Aligned with {cfg['htf_timeframe']})"

        # Filter 3: Candlestick Confirmation (Optional)
        if cfg['candlestick_confirmation_enabled']:
            confirming_pattern = self._get_candlestick_confirmation(signal_direction, min_reliability='Medium')
            if not confirming_pattern:
                logger.info(f"[{self.strategy_name}] Signal REJECTED: No confirming candlestick pattern found.")
                return None
            confirmations['candlestick_filter'] = f"Passed (Pattern: {confirming_pattern.get('name')})"

        logger.info(f"✨✨ [{self.strategy_name}] Signal for {signal_direction} confirmed by all filters! ✨✨")

        # --- 3. Calculate Risk Management ---
        entry_price = self.price_data.get('close')
        atr_data = self.get_indicator('atr')
        long_ema_val = ema_cross_data.get('values', {}).get('long_ema')

        if not all([entry_price, atr_data, long_ema_val]):
            logger.warning(f"[{self.strategy_name}] Could not calculate Stop Loss due to missing data.")
            return None
            
        atr_value = atr_data.get('values', {}).get('atr', 0)
        
        stop_loss = 0
        if signal_direction == "BUY":
            stop_loss = long_ema_val - (atr_value * cfg['atr_sl_multiplier'])
        else: # SELL
            stop_loss = long_ema_val + (atr_value * cfg['atr_sl_multiplier'])

        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        if not risk_params or not risk_params.get("targets"):
             logger.info(f"[{self.strategy_name}] Signal REJECTED: Could not calculate valid risk/reward targets.")
             return None

        # --- 4. Package and Return the Final Signal ---
        return {
            "direction": signal_direction,
            "entry_price": entry_price,
            **risk_params,
            "confirmations": confirmations
        }
