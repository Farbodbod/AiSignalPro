import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class ChandelierTrendRider(BaseStrategy):
    """
    ChandelierTrendRider - Definitive, World-Class, Toolkit-Powered Version
    -------------------------------------------------------------------------
    This is a professional trend-following strategy. It enters on a SuperTrend
    crossover and validates the signal through a multi-layered confirmation funnel.
    Crucially, it performs a pre-trade Risk-to-Reward check, only accepting
    setups with a favorable risk profile.
    
    The Funnel:
    1.  Signal: SuperTrend Crossover.
    2.  Filter 1: ADX confirms sufficient trend strength.
    3.  Filter 2 (Optional): Higher-timeframe trend is aligned.
    4.  Filter 3 (Optional): Volume confirms the move.
    5.  Filter 4 (Optional): Candlestick pattern supports the entry.
    6.  Final Check: The initial Risk-to-Reward ratio is acceptable.
    7.  Exit Management: Uses Chandelier Exit for a dynamic trailing stop.
    """
    strategy_name: str = "ChandelierTrendRider"

    def _get_signal_config(self) -> Dict[str, Any]:
        """Loads and validates the strategy's specific parameters from the config."""
        return {
            "st_period": int(self.config.get("supertrend_atr_period", 10)),
            "st_multiplier": float(self.config.get("supertrend_multiplier", 3.0)),
            "ch_atr_period": int(self.config.get("chandelier_atr_period", 22)),
            "ch_atr_multiplier": float(self.config.get("chandelier_atr_multiplier", 3.0)),
            "min_adx_strength": float(self.config.get("min_adx_strength", 25.0)),
            "min_rr_ratio": float(self.config.get("min_risk_reward_ratio", 1.2)),
            # --- Optional Filter Toggles ---
            "htf_confirmation_enabled": bool(self.config.get("htf_confirmation_enabled", True)),
            "htf_timeframe": str(self.config.get("htf_timeframe", "4h")),
            "volume_confirmation_enabled": bool(self.config.get("volume_confirmation_enabled", False)),
            "candlestick_confirmation_enabled": bool(self.config.get("candlestick_confirmation_enabled", False)),
        }

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self._get_signal_config()
        
        # --- 1. Get Primary Signal from SuperTrend Crossover ---
        supertrend_data = self.get_indicator('supertrend')
        if not supertrend_data or supertrend_data.get('status') != 'OK': return None

        st_signal = supertrend_data.get('analysis', {}).get('signal')
        signal_direction = None
        if st_signal == "Bullish Crossover": signal_direction = "BUY"
        elif st_signal == "Bearish Crossover": signal_direction = "SELL"
        else: return None
        
        logger.info(f"[{self.strategy_name}] Initial Signal: {signal_direction} from SuperTrend.")
        confirmations = {"entry_trigger": f"SuperTrend Crossover"}

        # --- 2. Confirmation Funnel ---
        # Filter 1: ADX Trend Strength
        adx_data = self.get_indicator('adx')
        if not adx_data or adx_data.get('status') != 'OK': return None
        adx_strength = adx_data.get('values', {}).get('adx', 0)
        if adx_strength < cfg['min_adx_strength']:
            logger.info(f"[{self.strategy_name}] Signal REJECTED: ADX strength ({adx_strength:.2f}) is below threshold.")
            return None
        confirmations['adx_filter'] = f"Passed (ADX: {adx_strength:.2f})"

        # Filter 2: Higher-Timeframe Confirmation
        if cfg['htf_confirmation_enabled']:
            if not self._get_trend_confirmation(signal_direction, cfg['htf_timeframe']):
                logger.info(f"[{self.strategy_name}] Signal REJECTED: Not aligned with {cfg['htf_timeframe']} trend.")
                return None
            confirmations['htf_filter'] = f"Passed (Aligned with {cfg['htf_timeframe']})"

        # Filter 3: Volume Confirmation
        if cfg['volume_confirmation_enabled']:
            if not self._get_volume_confirmation():
                logger.info(f"[{self.strategy_name}] Signal REJECTED: Lacks significant volume confirmation.")
                return None
            confirmations['volume_filter'] = "Passed (Whale activity detected)"

        # Filter 4: Candlestick Confirmation
        if cfg['candlestick_confirmation_enabled']:
            confirming_pattern = self._get_candlestick_confirmation(signal_direction)
            if not confirming_pattern:
                logger.info(f"[{self.strategy_name}] Signal REJECTED: No confirming candlestick pattern.")
                return None
            confirmations['candlestick_filter'] = f"Passed (Pattern: {confirming_pattern.get('name')})"

        # --- 3. Calculate Risk & Perform Pre-Trade R/R Check ---
        entry_price = self.price_data.get('close')
        chandelier_data = self.get_indicator('chandelier_exit')
        if not all([entry_price, chandelier_data]) or chandelier_data.get('status') != 'OK': return None
        
        stop_loss_key = 'long_stop' if signal_direction == "BUY" else 'short_stop'
        stop_loss = chandelier_data.get('values', {}).get(stop_loss_key)
        if not stop_loss: return None
            
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        
        # Final and most important check
        if not risk_params or risk_params.get("risk_reward_ratio", 0) < cfg['min_rr_ratio']:
            rr_ratio = risk_params.get("risk_reward_ratio", 0)
            logger.info(f"[{self.strategy_name}] Signal REJECTED: Initial R/R ratio ({rr_ratio}) is below threshold ({cfg['min_rr_ratio']}).")
            return None
        confirmations['rr_check'] = f"Passed (R/R: {risk_params.get('risk_reward_ratio')})"

        logger.info(f"✨✨ [{self.strategy_name}] TREND RIDER SIGNAL CONFIRMED! ✨✨")
        
        # --- 4. Package and Return the Final Signal ---
        return {
            "direction": signal_direction,
            "entry_price": entry_price,
            **risk_params,
            "confirmations": confirmations
        }
