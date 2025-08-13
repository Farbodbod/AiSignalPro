import logging
import pandas as pd
from typing import Dict, Any, Optional

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class ChandelierTrendRider(BaseStrategy):
    """
    ChandelierTrendRider - (v4.2 - Final Harmonization)
    -------------------------------------------------------------------------
    This definitive version adds the standard _get_signal_config method and
    corrects the position sizing logic to be fully compatible and harmonized
    with the BaseStrategy v5.1 framework and the Universal Conductor.
    """
    strategy_name: str = "ChandelierTrendRider"

    default_config = {
        "min_adx_strength": 25.0,
        "target_atr_multiples": [2.0, 4.0, 6.0],
        "risk_per_trade_percent": 0.01,
        "session_filter": {
            "enabled": True,
            "active_hours_utc": [[8, 16], [13, 21]]
        },
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {
            "min_required_score": 2,
            "adx": {"weight": 1, "min_strength": 25},
            "supertrend": {"weight": 1}
        }
    }
    
    # ✅ FIX: Added the standard, hierarchical config loader method.
    def _get_signal_config(self) -> Dict[str, Any]:
        """ Loads the hierarchical config based on the current timeframe. """
        base_configs = self.config.get("default_params", self.config)
        tf_overrides = self.config.get("timeframe_overrides", {}).get(self.primary_timeframe, {})
        return {**base_configs, **tf_overrides}

    def _is_in_active_session(self, cfg: Dict[str, Any]) -> bool:
        """ The Market Session Engine, now using robust timestamp parsing. """
        session_cfg = cfg.get('session_filter', {})
        if not session_cfg.get('enabled', False):
            return True

        if not self.price_data: return False
        candle_timestamp = self.price_data.get('timestamp')
        if not candle_timestamp: return False
        
        parsed_timestamp = pd.to_datetime(candle_timestamp, errors='coerce')
        if pd.isna(parsed_timestamp):
            logger.warning(f"[{self.strategy_name}] Could not parse candle timestamp '{candle_timestamp}' for session filter.")
            return False

        candle_hour = parsed_timestamp.hour
        
        active_windows = session_cfg.get('active_hours_utc', [])
        for window in active_windows:
            if len(window) == 2 and window[0] <= candle_hour < window[1]:
                return True
        return False

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self._get_signal_config() # This now correctly loads adaptive parameters
        
        if not self.price_data or not self._is_in_active_session(cfg):
            return None
            
        supertrend_data = self.get_indicator('supertrend')
        adx_data = self.get_indicator('adx')
        chandelier_data = self.get_indicator('chandelier_exit')
        bollinger_data = self.get_indicator('bollinger')
        atr_data = self.get_indicator('atr')
        
        if not all([supertrend_data, adx_data, chandelier_data, bollinger_data, atr_data]):
            return None

        if not bollinger_data['analysis'].get('is_squeeze_release', False):
            return None
        
        st_signal = supertrend_data.get('analysis', {}).get('signal')
        signal_direction = "BUY" if "Bullish Crossover" in st_signal else "SELL" if "Bearish Crossover" in st_signal else None
        if not signal_direction: return None
        
        confirmations = {"entry_trigger": "SuperTrend Crossover after Squeeze", "session": "Active"}

        adx_strength = adx_data.get('values', {}).get('adx', 0)
        dmi_plus = adx_data.get('values', {}).get('plus_di', 0)
        dmi_minus = adx_data.get('values', {}).get('minus_di', 0)
        is_trend_strong = adx_strength >= cfg.get('min_adx_strength', 25.0)
        is_dir_confirmed = (signal_direction == "BUY" and dmi_plus > dmi_minus) or \
                           (signal_direction == "SELL" and dmi_minus > dmi_plus)
        if not (is_trend_strong and is_dir_confirmed): return None
        confirmations['adx_dmi_filter'] = f"Passed (ADX: {adx_strength:.2f}, Dir Confirmed)"

        if cfg.get('htf_confirmation_enabled'):
            if not self._get_trend_confirmation(signal_direction): return None
            confirmations['htf_filter'] = "Passed (HTF Aligned)"

        entry_price = self.price_data.get('close')
        if not entry_price: return None
        
        stop_loss_key = 'long_stop' if signal_direction == "BUY" else 'short_stop'
        stop_loss = chandelier_data.get('values', {}).get(stop_loss_key)
        atr_value = atr_data.get('values', {}).get('atr')
        if not all([stop_loss, atr_value]): return None

        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        if not risk_params or not risk_params.get("targets"): return None
            
        # ✅ FIX: Position Sizing logic now correctly uses the main_config for global parameters
        account_equity = float(self.main_config.get("general", {}).get("account_equity", 10000))
        risk_per_trade = cfg.get("risk_per_trade_percent", 0.01)
        fees_pct = self.main_config.get("general", {}).get("assumed_fees_pct", 0.001)
        slippage_pct = self.main_config.get("general", {}).get("assumed_slippage_pct", 0.0005)
        
        total_risk_per_unit = abs(entry_price - stop_loss) + (entry_price * fees_pct) + (entry_price * slippage_pct)
        position_size = (account_equity * risk_per_trade) / total_risk_per_unit if total_risk_per_unit > 0 else 0

        logger.info(f"✨✨ [{self.strategy_name}] MARKET SESSION SIGNAL CONFIRMED! ✨✨")
        
        return {
            "direction": signal_direction,
            "entry_price": entry_price,
            "position_size_units": round(position_size, 8),
            **risk_params,
            "confirmations": confirmations
        }
