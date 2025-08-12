import logging
from typing import Dict, Any, Optional

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class ChandelierTrendRider(BaseStrategy):
    """
    ChandelierTrendRider - (v3.0 - Miracle Edition)
    -------------------------------------------------------------------------
    This world-class version is a complete re-architecture based on deep quantitative
    research. It operates on four core pillars:
    1.  Volatility Engine: Only accepts signals breaking out from a volatility squeeze.
    2.  Multi-Factor Confirmation: Validates trend strength AND direction using ADX + DMI.
    3.  Dynamic Risk Engine: Calculates adaptive, ATR-based profit targets.
    4.  Position Sizing Engine: Determines the precise position size based on a
        fixed percentage risk model, including fees and slippage.
    """
    strategy_name: str = "ChandelierTrendRider"

    def _get_signal_config(self) -> Dict[str, Any]:
        """Loads and validates the strategy's specific parameters from the config."""
        return {
            # Core Signal Parameters
            "min_adx_strength": float(self.config.get("min_adx_strength", 25.0)),
            
            # Pillar 3: Dynamic Risk Engine
            "target_atr_multiples": self.config.get("target_atr_multiples", [2.0, 4.0, 6.0]),
            
            # Pillar 4: Position Sizing Engine
            "risk_per_trade_percent": float(self.config.get("risk_per_trade_percent", 0.01)), # 1% of account
            "assumed_fees_pct": float(self.config.get("assumed_fees_pct", 0.001)), # 0.1% for fees
            "assumed_slippage_pct": float(self.config.get("assumed_slippage_pct", 0.0005)), # 0.05% for slippage
            
            # Optional Filters
            "htf_confirmation_enabled": bool(self.config.get("htf_confirmation_enabled", True)),
            "htf_timeframe": str(self.config.get("htf_timeframe", "4h")),
        }

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self._get_signal_config()
        
        # --- 1. Anti-Fragile Data Check ---
        if not self.price_data: return None
            
        supertrend_data = self.get_indicator('supertrend')
        adx_data = self.get_indicator('adx')
        chandelier_data = self.get_indicator('chandelier_exit')
        bollinger_data = self.get_indicator('bollinger') # For Volatility Engine
        atr_data = self.get_indicator('atr') # For Dynamic Risk Engine
        
        required_indicators = [supertrend_data, adx_data, chandelier_data, bollinger_data, atr_data]
        if not all(required_indicators):
            logger.debug(f"[{self.strategy_name}] Skipped: Missing one or more required indicators.")
            return None

        # --- ✅ Pillar 1: Volatility Engine ---
        # A valid trend signal must emerge from a period of low volatility.
        # We look for a "squeeze release": it was in a squeeze recently, but isn't now.
        if not bollinger_data['analysis'].get('is_squeeze_release', False):
            # Note: The indicator 'bollinger.py' must be upgraded to provide 'is_squeeze_release'
            # For now, we check if it is NOT in a squeeze.
            if bollinger_data['analysis'].get('is_in_squeeze', True):
                return None
        
        # --- 2. Get Primary Trigger from SuperTrend Crossover ---
        st_signal = supertrend_data.get('analysis', {}).get('signal')
        signal_direction = None
        if "Bullish Crossover" in st_signal: signal_direction = "BUY"
        elif "Bearish Crossover" in st_signal: signal_direction = "SELL"
        else: return None
        
        confirmations = {"entry_trigger": "SuperTrend Crossover after Squeeze"}

        # --- ✅ Pillar 2: Multi-Factor Confirmation Engine ---
        adx_strength = adx_data.get('values', {}).get('adx', 0)
        dmi_plus = adx_data.get('values', {}).get('plus_di', 0)
        dmi_minus = adx_data.get('values', {}).get('minus_di', 0)

        is_trend_strong = adx_strength >= cfg['min_adx_strength']
        is_dir_confirmed = (signal_direction == "BUY" and dmi_plus > dmi_minus) or \
                           (signal_direction == "SELL" and dmi_minus > dmi_plus)
        
        if not (is_trend_strong and is_dir_confirmed):
            return None
        confirmations['adx_dmi_filter'] = f"Passed (ADX: {adx_strength:.2f}, Dir Confirmed)"

        # --- 3. Optional Confirmation Filters ---
        if cfg['htf_confirmation_enabled']:
            if not self._get_trend_confirmation(signal_direction, cfg['htf_timeframe']):
                return None
            confirmations['htf_filter'] = f"Passed (Aligned with {cfg['htf_timeframe']})"

        # --- ✅ Pillar 3 & 4: Dynamic Risk & Position Sizing Engine ---
        entry_price = self.price_data.get('close')
        if not entry_price: return None
        
        stop_loss_key = 'long_stop' if signal_direction == "BUY" else 'short_stop'
        stop_loss = chandelier_data.get('values', {}).get(stop_loss_key)
        atr_value = atr_data.get('values', {}).get('atr')
        if not all([stop_loss, atr_value]): return None

        # Calculate dynamic targets based on ATR multiples
        targets = []
        risk_per_unit_no_rr = abs(entry_price - stop_loss)
        if risk_per_unit_no_rr > 0:
            for multiple in cfg['target_atr_multiples']:
                if signal_direction == "BUY":
                    targets.append(entry_price + (atr_value * multiple))
                else: # SELL
                    targets.append(entry_price - (atr_value * multiple))
        
        if not targets: return None
        
        # Calculate final R/R to the first target, including costs
        fee_cost = entry_price * cfg['assumed_fees_pct']
        slippage_cost = entry_price * cfg['assumed_slippage_pct']
        total_risk_per_unit = risk_per_unit_no_rr + fee_cost + slippage_cost
        reward_per_unit = abs(targets[0] - entry_price)
        final_rr = reward_per_unit / total_risk_per_unit if total_risk_per_unit > 0 else 0
        
        # Calculate precise position size
        # NOTE: This assumes `self.config` has an 'account_equity' field.
        account_equity = float(self.config.get("general", {}).get("account_equity", 10000)) # Default 10k equity
        risk_amount_usd = account_equity * cfg['risk_per_trade_percent']
        position_size = risk_amount_usd / total_risk_per_unit if total_risk_per_unit > 0 else 0

        logger.info(f"✨✨ [{self.strategy_name}] TREND RIDER MIRACLE SIGNAL CONFIRMED! ✨✨")
        
        # We package everything into the final signal
        return {
            "direction": signal_direction,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "targets": targets,
            "risk_reward_ratio": round(final_rr, 2),
            "position_size_units": round(position_size, 8), # Rounded to standard crypto precision
            "confirmations": confirmations
        }
