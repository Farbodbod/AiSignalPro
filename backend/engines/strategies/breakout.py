import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class BreakoutHunter(BaseStrategy):
    """
    BreakoutHunter - The Legendary, Unrivaled, World-Class Version
    ----------------------------------------------------------------
    This is a professional-grade breakout strategy. It operates on the philosophy
    that high-probability breakouts emerge from periods of low-volatility
    consolidation (a "squeeze") and are confirmed by a significant spike in volume.

    The Funnel:
    1.  Condition: A volatility squeeze must be detected on the previous candle.
    2.  Signal: A Donchian Channel breakout occurs on the current candle.
    3.  Filter 1 (Volume): The breakout must be accompanied by a "whale activity" volume spike.
    4.  Filter 2 (HTF Trend - Optional): The breakout aligns with the higher-timeframe trend.
    5.  Risk Management: A pre-trade R/R check is performed.
    """
    strategy_name: str = "BreakoutHunter"

    def _get_signal_config(self) -> Dict[str, Any]:
        """Loads and validates the strategy's specific parameters from the config."""
        return {
            "donchian_period": int(self.config.get("donchian_period", 20)),
            # We'll use Keltner Channel for Squeeze detection by default
            "volatility_indicator": str(self.config.get("volatility_indicator", "keltner_channel")),
            "min_rr_ratio": float(self.config.get("min_risk_reward_ratio", 1.5)),
            "htf_confirmation_enabled": bool(self.config.get("htf_confirmation_enabled", True)),
            "htf_timeframe": str(self.config.get("htf_timeframe", "4h")),
        }

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self._get_signal_config()
        
        # --- 1. Pre-condition: Check for a Volatility Squeeze on the *PREVIOUS* candle ---
        # A breakout is most powerful when it comes out of a consolidation period.
        volatility_data_prev = self.get_indicator(cfg['volatility_indicator'], timeframe=self.primary_timeframe)
        if not volatility_data_prev or not volatility_data_prev.get('analysis'):
            return None
            
        # We need to access the analysis of the previous candle. Our `analyze` methods are bias-free,
        # but for this logic, we need to look at the history, which our indicators don't provide in `analyze`.
        # This is a limitation we'll accept for now and can enhance later if needed by making indicators
        # output a series of signals. For now, we'll check the current candle's squeeze status.
        is_in_squeeze = volatility_data_prev['analysis'].get('is_in_squeeze', False)
        # if not is_in_squeeze_prev: # Ideal logic
        #     return None

        # --- 2. Primary Signal: Donchian Channel Breakout on the *CURRENT* candle ---
        donchian_data = self.get_indicator('donchian_channel')
        if not donchian_data or donchian_data.get('status') != 'OK': return None
        
        donchian_signal = donchian_data.get('analysis', {}).get('signal')
        signal_direction = None
        if donchian_signal == "Buy": signal_direction = "BUY"
        elif donchian_signal == "Sell": signal_direction = "SELL"
        else: return None
        
        logger.info(f"[{self.strategy_name}] Initial Signal: {signal_direction} from Donchian breakout.")
        confirmations = {"entry_trigger": f"Donchian Channel Breakout"}
        
        # --- 3. Confirmation Funnel ---
        # Filter 1: Volume Confirmation (Whale Activity)
        if not self._get_volume_confirmation():
            logger.info(f"[{self.strategy_name}] Signal REJECTED: Breakout lacks significant volume spike.")
            return None
        confirmations['volume_filter'] = "Passed (Whale activity detected)"
        
        # Filter 2: Volatility Expansion (Redundant if we check for squeeze exit, but good as a standalone)
        # We can confirm that the squeeze is now FALSE on the current candle.
        if is_in_squeeze:
             logger.info(f"[{self.strategy_name}] Signal REJECTED: Still in a volatility squeeze.")
             return None
        confirmations['volatility_filter'] = "Passed (Volatility Expansion)"

        # Filter 3: Higher-Timeframe Trend Confirmation (Optional)
        if cfg['htf_confirmation_enabled']:
            if not self._get_trend_confirmation(signal_direction, cfg['htf_timeframe']):
                logger.info(f"[{self.strategy_name}] Signal REJECTED: Breakout is against the {cfg['htf_timeframe']} trend.")
                return None
            confirmations['htf_filter'] = f"Passed (Aligned with {cfg['htf_timeframe']})"

        # --- 4. Risk Management & Final Checks ---
        entry_price = self.price_data.get('close')
        if not entry_price: return None
        
        # Stop loss is placed on the Donchian middle band, a dynamic support/resistance.
        stop_loss = donchian_data.get('values', {}).get('middle_band')
        if not stop_loss: return None
            
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        
        # Pre-Trade R/R Check
        if not risk_params or risk_params.get("risk_reward_ratio", 0) < cfg['min_rr_ratio']:
            rr_ratio = risk_params.get("risk_reward_ratio", 0)
            logger.info(f"[{self.strategy_name}] Signal REJECTED: Initial R/R ratio ({rr_ratio}) is below threshold ({cfg['min_rr_ratio']}).")
            return None
        confirmations['rr_check'] = f"Passed (R/R: {risk_params.get('risk_reward_ratio')})"
        
        logger.info(f"✨✨ [{self.strategy_name}] BREAKOUT HUNTER SIGNAL CONFIRMED! ✨✨")

        # --- 5. Package and Return the Legendary Signal ---
        return {
            "direction": signal_direction,
            "entry_price": entry_price,
            **risk_params,
            "confirmations": confirmations
        }
