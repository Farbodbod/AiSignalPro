import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class ChandelierTrendRider(BaseStrategy):
    """
    ChandelierTrendRider - (v4.0 - Market Session Edition)
    -------------------------------------------------------------------------
    This world-class version adds a fifth pillar of intelligence: a Market
    Session Engine. It learns to operate only during peak liquidity hours,
    avoiding low-volatility periods and dramatically increasing the quality
    and probability of its trend-following signals.
    """
    strategy_name: str = "ChandelierTrendRider"

    # ✅ MIRACLE UPGRADE: Default config now includes the Market Session Engine
    default_config = {
        "min_adx_strength": 25.0,
        "target_atr_multiples": [2.0, 4.0, 6.0],
        "risk_per_trade_percent": 0.01,
        "assumed_fees_pct": 0.001,
        "assumed_slippage_pct": 0.0005,
        "session_filter": {
            "enabled": True,
            "active_hours_utc": [[8, 16], [20, 22]] # Default: London Session & NY Close
        },
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {
            "min_required_score": 2,
            "adx": {"weight": 1, "min_strength": 25},
            "supertrend": {"weight": 1}
        }
    }

    def _is_in_active_session(self) -> bool:
        """
        ✅ MIRACLE UPGRADE: The Market Session Engine.
        Checks if the current candle's timestamp is within the active trading hours.
        """
        session_cfg = self.config.get('session_filter', {})
        if not session_cfg.get('enabled', False):
            return True # If filter is disabled, always proceed

        candle_timestamp = self.price_data.get('timestamp')
        if not candle_timestamp: return False # Cannot check session without a timestamp
        
        # Convert string timestamp to datetime object if needed (assuming UTC)
        try:
            # Pandas Timestamps are timezone-aware if the source is.
            # We will work with the hour component in UTC.
            candle_hour = pd.to_datetime(candle_timestamp).hour
        except Exception:
            logger.warning(f"[{self.strategy_name}] Could not parse candle timestamp for session filter.")
            return False

        active_windows = session_cfg.get('active_hours_utc', [])
        for window in active_windows:
            if len(window) == 2 and window[0] <= candle_hour < window[1]:
                return True
        
        logger.debug(f"[{self.strategy_name}] Signal REJECTED: Outside of active trading sessions (Hour UTC: {candle_hour}).")
        return False

    def check_signal(self) -> Optional[Dict[str, Any]]:
        # --- ✅ Pillar 0: Anti-Fragile Data & Time Check ---
        if not self.price_data: return None
            
        if not self._is_in_active_session():
            return None # Exit immediately if not in an active session

        # The rest of the checks proceed only if the session is active
        supertrend_data = self.get_indicator('supertrend')
        adx_data = self.get_indicator('adx')
        chandelier_data = self.get_indicator('chandelier_exit')
        bollinger_data = self.get_indicator('bollinger')
        atr_data = self.get_indicator('atr')
        
        if not all([supertrend_data, adx_data, chandelier_data, bollinger_data, atr_data]):
            return None

        # --- Pillar 1: Volatility Engine ---
        if not bollinger_data['analysis'].get('is_squeeze_release', False):
            return None
        
        # --- 2. Get Primary Trigger from SuperTrend Crossover ---
        st_signal = supertrend_data.get('analysis', {}).get('signal')
        signal_direction = None
        if "Bullish Crossover" in st_signal: signal_direction = "BUY"
        elif "Bearish Crossover" in st_signal: signal_direction = "SELL"
        else: return None
        
        confirmations = {"entry_trigger": "SuperTrend Crossover after Squeeze", "session": "Active"}

        # --- Pillar 2: Multi-Factor Confirmation Engine ---
        adx_strength = adx_data.get('values', {}).get('adx', 0)
        dmi_plus = adx_data.get('values', {}).get('plus_di', 0)
        dmi_minus = adx_data.get('values', {}).get('minus_di', 0)
        is_trend_strong = adx_strength >= self.config.get('min_adx_strength', 25.0)
        is_dir_confirmed = (signal_direction == "BUY" and dmi_plus > dmi_minus) or \
                           (signal_direction == "SELL" and dmi_minus > dmi_plus)
        if not (is_trend_strong and is_dir_confirmed): return None
        confirmations['adx_dmi_filter'] = f"Passed (ADX: {adx_strength:.2f}, Dir Confirmed)"

        # --- 3. Optional HTF Confirmation ---
        if self.config.get('htf_confirmation_enabled'):
            if not self._get_trend_confirmation(signal_direction): return None
            confirmations['htf_filter'] = "Passed (HTF Aligned)"

        # --- Pillar 3 & 4: Dynamic Risk & Position Sizing Engine ---
        entry_price = self.price_data.get('close')
        if not entry_price: return None
        
        stop_loss_key = 'long_stop' if signal_direction == "BUY" else 'short_stop'
        stop_loss = chandelier_data.get('values', {}).get(stop_loss_key)
        atr_value = atr_data.get('values', {}).get('atr')
        if not all([stop_loss, atr_value]): return None

        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        
        # The base method now includes costs, so we only need to check the final R/R
        if not risk_params or risk_params.get("risk_reward_ratio", 0) < 1.0: # Basic check for positive R/R
            return None
            
        # Position Sizing
        account_equity = float(self.config.get("general", {}).get("account_equity", 10000))
        risk_per_trade = self.config.get("risk_per_trade_percent", 0.01)
        total_risk_per_unit = abs(entry_price - stop_loss)
        if total_risk_per_unit > 0:
            position_size = (account_equity * risk_per_trade) / total_risk_per_unit
        else:
            position_size = 0

        logger.info(f"✨✨ [{self.strategy_name}] MARKET SESSION SIGNAL CONFIRMED! ✨✨")
        
        return {
            "direction": signal_direction,
            "entry_price": entry_price,
            "position_size_units": round(position_size, 8),
            **risk_params,
            "confirmations": confirmations
        }
