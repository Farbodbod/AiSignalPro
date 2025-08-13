import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class VwapMeanReversion(BaseStrategy):
    """
    VwapMeanReversion - (v3.1 - Hotfix & Final)
    --------------------------------------------------------------------------------------
    This definitive version fixes a critical AttributeError by correctly implementing
    the _get_signal_config method, fully aligning it with the BaseStrategy v5.1 framework.
    """
    strategy_name: str = "VwapMeanReversion"

    # The default_config remains the same and is correct.
    default_config = {
        "max_adx_for_reversion": 25.0,
        "min_rr_ratio": 2.0,
        "oscillator_logic": "AND",
        "use_rsi": True, "rsi_oversold": 30.0, "rsi_overbought": 70.0,
        "use_williams_r": True, "williams_r_oversold": -80.0, "williams_r_overbought": -20.0,
        "atr_sl_multiplier": 1.5,
        "require_candle_confirmation": True,
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {
            "min_required_score": 1,
            "adx": {"weight": 1, "min_strength": 25}
        }
    }
    
    # ✅ FIX: The missing _get_signal_config method is now correctly implemented.
    def _get_signal_config(self) -> Dict[str, Any]:
        """
        Loads the strategy's configuration. This implementation is compatible
        with the hierarchical structure of the BaseStrategy framework.
        """
        # For this strategy, we don't have timeframe_overrides, so we just use the main config.
        # This standard pattern makes it future-proof.
        base_configs = self.config.get("default_params", self.config) # Fallback for flat structure
        tf_overrides = self.config.get("timeframe_overrides", {}).get(self.primary_timeframe, {})
        return {**base_configs, **tf_overrides}

    def _get_oscillator_confirmation(self, direction: str, cfg: Dict, rsi_data: Optional[Dict], wr_data: Optional[Dict]) -> bool:
        """ The robust oscillator confirmation engine. """
        rsi_confirm = False
        if cfg.get('use_rsi') and rsi_data:
            rsi_val = rsi_data.get('values', {}).get('rsi')
            if rsi_val is not None:
                if direction == "BUY" and rsi_val < cfg['rsi_oversold']: rsi_confirm = True
                elif direction == "SELL" and rsi_val > cfg['rsi_overbought']: rsi_confirm = True

        wr_confirm = False
        if cfg.get('use_williams_r') and wr_data:
            wr_val = wr_data.get('values', {}).get('wr')
            if wr_val is not None:
                if direction == "BUY" and wr_val < cfg['williams_r_oversold']: wr_confirm = True
                elif direction == "SELL" and wr_val > cfg['williams_r_overbought']: wr_confirm = True
        
        if cfg.get('oscillator_logic') == "AND":
            checks = []
            if cfg.get('use_rsi'): checks.append(rsi_confirm)
            if cfg.get('use_williams_r'): checks.append(wr_confirm)
            return all(checks) if checks else False
        elif cfg.get('oscillator_logic') == "OR":
            return rsi_confirm or wr_confirm
        return False

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self._get_signal_config() # This line will now work correctly.
        if not self.price_data: return None

        indicators = {name: self.get_indicator(name) for name in ['vwap_bands', 'atr', 'adx', 'rsi', 'williams_r']}
        if not all([indicators.get('vwap_bands'), indicators.get('atr'), indicators.get('adx')]):
            return None

        adx_data = indicators['adx']
        adx_strength = adx_data.get('values', {}).get('adx', 100)
        if adx_strength > cfg.get('max_adx_for_reversion', 25.0):
            return None

        vwap_data = indicators['vwap_bands']
        vwap_position = vwap_data.get('analysis', {}).get('position')
        signal_direction = None
        if "Below" in vwap_position: signal_direction = "BUY"
        elif "Above" in vwap_position: signal_direction = "SELL"
        else: return None
        
        confirmations = {"trigger": f"Price {vwap_position}", "market_regime": f"Ranging (ADX: {adx_strength:.2f})"}

        if not self._get_oscillator_confirmation(signal_direction, cfg, indicators['rsi'], indicators['williams_r']):
            return None
        confirmations['oscillator_filter'] = f"Passed (Logic: {cfg.get('oscillator_logic')})"

        if cfg.get('require_candle_confirmation'):
            if not self._get_candlestick_confirmation(signal_direction, min_reliability='Medium'): return None
            confirmations['candlestick_filter'] = "Passed"

        if cfg.get('htf_confirmation_enabled'):
            opposite_direction = "SELL" if signal_direction == "BUY" else "BUY"
            if self._get_trend_confirmation(opposite_direction): return None
            confirmations['htf_filter'] = "Passed (No strong opposing trend)"

        entry_price = self.price_data.get('close')
        vwap_values = vwap_data.get('values', {})
        if not entry_price: return None
        
        atr_value = indicators['atr'].get('values', {}).get('atr', entry_price * 0.01)
        
        stop_loss = 0
        if signal_direction == "BUY":
            lower_band = vwap_values.get('lower_band')
            if not lower_band: return None
            stop_loss = lower_band - (atr_value * cfg.get('atr_sl_multiplier', 1.5))
        else: # SELL
            upper_band = vwap_values.get('upper_band')
            if not upper_band: return None
            stop_loss = upper_band + (atr_value * cfg.get('atr_sl_multiplier', 1.5))
        
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        
        vwap_line = vwap_values.get('vwap')
        if vwap_line and risk_params.get('targets'):
            risk_params['targets'][0] = vwap_line
            risk_amount = abs(entry_price - stop_loss)
            if risk_amount > 1e-9:
                risk_params['risk_reward_ratio'] = round(abs(vwap_line - entry_price) / risk_amount, 2)
        
        if not risk_params or risk_params.get("risk_reward_ratio", 0) < cfg.get('min_rr_ratio', 1.8): return None
        confirmations['rr_check'] = f"Passed (R/R to VWAP: {risk_params.get('risk_reward_ratio')})"
        
        logger.info(f"✨✨ [{self.strategy_name}] VWAP MEAN REVERSION SIGNAL CONFIRMED! ✨✨")

        return { "direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations }

