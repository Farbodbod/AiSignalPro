import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class TrendRiderPro(BaseStrategy):
    """
    TrendRiderPro - Definitive, World-Class, and Toolkit-Powered Version
    ---------------------------------------------------------------------
    This advanced trend-following strategy utilizes the powerful toolkit from
    BaseStrategy to create clean, readable, and robust trading logic.
    It identifies a trend entry, validates it with multiple filters (ADX, Price-MA,
    optional HTF, optional Volume), and uses Chandelier Exit for dynamic risk management.
    """
    strategy_name: str = "TrendRiderPro"

    def _get_signal_config(self) -> Dict[str, Any]:
        """Loads and validates the strategy's specific parameters from the config."""
        return {
            "entry_trigger_type": self.config.get("entry_trigger_type", "supertrend"), # 'supertrend' or 'ema_cross'
            # EMA Cross Params
            "ema_short_period": int(self.config.get("ema_short_period", 9)),
            "ema_long_period": int(self.config.get("ema_long_period", 21)),
            # SuperTrend Params
            "st_period": int(self.config.get("supertrend_atr_period", 10)),
            "st_multiplier": float(self.config.get("supertrend_multiplier", 3.0)),
            # Chandelier Exit (Stop Loss) Params
            "ch_atr_period": int(self.config.get("chandelier_atr_period", 22)),
            "ch_atr_multiplier": float(self.config.get("chandelier_atr_multiplier", 3.0)),
            # Filter Params
            "min_adx_strength": float(self.config.get("min_adx_strength", 25.0)),
            "trend_filter_ma_period": int(self.config.get("trend_filter_ma_period", 50)),
            "trend_filter_ma_type": str(self.config.get("trend_filter_ma_type", "DEMA")).upper(),
            # Higher Timeframe Confirmation Filter
            "htf_confirmation_enabled": bool(self.config.get("htf_confirmation_enabled", True)),
            "htf_timeframe": str(self.config.get("htf_timeframe", "4h")),
        }

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self._get_signal_config()
        
        # --- 1. Get Primary Entry Signal ---
        signal_direction, entry_trigger_name = self._get_primary_signal(cfg)
        if not signal_direction:
            return None

        # --- 2. Apply Filters ---
        # ✨ ADX Strength Filter
        adx_data = self.get_indicator('adx')
        if not adx_data or adx_data.get('status') != 'OK': return None
        adx_strength = adx_data.get('values', {}).get('adx', 0)
        if adx_strength < cfg['min_adx_strength']:
            logger.info(f"[{self.strategy_name}] Signal rejected: ADX strength ({adx_strength:.2f}) is below threshold ({cfg['min_adx_strength']}).")
            return None

        # ✨ Price vs. Fast MA Trend Filter
        ma_filter_data = self.get_indicator('fast_ma')
        if ma_filter_data and ma_filter_data.get('status') == 'OK':
            ma_value = ma_filter_data.get('values', {}).get('ma_value', 0)
            current_price = self.price_data.get('close', 0)
            if (signal_direction == "BUY" and current_price < ma_value) or \
               (signal_direction == "SELL" and current_price > ma_value):
                logger.info(f"[{self.strategy_name}] Signal rejected: Price is on the wrong side of the trend filter MA.")
                return None
        
        # ✨ Higher Timeframe Trend Confirmation Filter (Optional)
        if cfg['htf_confirmation_enabled']:
            if not self._get_trend_confirmation(signal_direction, cfg['htf_timeframe']):
                logger.info(f"[{self.strategy_name}] Signal rejected: Trend confirmation failed on {cfg['htf_timeframe']}.")
                return None
        
        # --- 3. Calculate Risk Management ---
        entry_price = self.price_data.get('close')
        chandelier_data = self.get_indicator('chandelier_exit')
        if not chandelier_data or chandelier_data.get('status') != 'OK': return None
        
        stop_loss_key = 'long_stop' if signal_direction == "BUY" else 'short_stop'
        stop_loss = chandelier_data.get('values', {}).get(stop_loss_key)

        if not stop_loss: return None
            
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        # Final quality check for Risk/Reward
        if not risk_params or not risk_params.get("targets"):
             logger.info(f"[{self.strategy_name}] Signal rejected: Could not calculate valid risk/reward targets.")
             return None

        # --- 4. Package the Final Signal ---
        logger.info(f"✨✨ [{self.strategy_name}] Signal for {signal_direction} confirmed by all filters! ✨✨")
        
        confirmations = {
            "entry_trigger": entry_trigger_name,
            "strength_filter": f"ADX > {cfg['min_adx_strength']} (Value: {adx_strength:.2f})",
            "trend_filter": f"Price confirmed by {cfg['trend_filter_ma_type']}({cfg['trend_filter_ma_period']})",
            "htf_confirmation": f"Confirmed by {cfg['htf_timeframe']} trend" if cfg['htf_confirmation_enabled'] else "Disabled",
            "exit_management": f"Chandelier Stop Loss"
        }
        
        return {
            "direction": signal_direction,
            "entry_price": entry_price,
            **risk_params,
            "confirmations": confirmations
        }

    def _get_primary_signal(self, cfg: Dict[str, Any]) -> tuple[Optional[str], str]:
        """ Determines the initial BUY or SELL signal based on the configured entry trigger. """
        if cfg['entry_trigger_type'] == 'ema_cross':
            trigger_name = f"EMA Cross ({cfg['ema_short_period']}/{cfg['ema_long_period']})"
            ema_cross_data = self.get_indicator('ema_cross')
            if ema_cross_data and ema_cross_data.get('status') == 'OK':
                signal = ema_cross_data.get('analysis', {}).get('signal')
                if signal in ['Buy', 'Sell']:
                    return signal.upper(), trigger_name
        else: # Default to supertrend
            trigger_name = f"SuperTrend ({cfg['st_period']},{cfg['st_multiplier']})"
            supertrend_data = self.get_indicator('supertrend')
            if supertrend_data and supertrend_data.get('status') == 'OK':
                signal = supertrend_data.get('analysis', {}).get('signal')
                if signal == "Bullish Crossover": return "BUY", trigger_name
                if signal == "Bearish Crossover": return "SELL", trigger_name
                
        return None, ""
