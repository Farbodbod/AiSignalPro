import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class VwapMeanReversion(BaseStrategy):
    """
    VwapMeanReversion - (v3.0 - Market Regime Edition)
    --------------------------------------------------------------------------------------
    This world-class version is now a market diagnostics expert. It features:
    1.  Market Regime Filter: Uses ADX to detect strong trends and intelligently
        disables itself, as mean-reversion is for ranging markets.
    2.  Robust Oscillator Engine: Handles complex AND/OR logic for confirmations gracefully.
    3.  Professional-Grade Risk Parameters: Enforces a higher default R/R ratio.
    """
    strategy_name: str = "VwapMeanReversion"

    # ✅ MIRACLE UPGRADE: Default configuration for the new engines
    default_config = {
        "max_adx_for_reversion": 25.0, # Strategy is active only if ADX is below this
        "min_rr_ratio": 1.8,
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

    def _get_oscillator_confirmation(self, direction: str, cfg: Dict, rsi_data: Optional[Dict], wr_data: Optional[Dict]) -> bool:
        """ ✅ Upgraded: More robust oscillator confirmation engine. """
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
        cfg = self._get_signal_config()
        if not self.price_data: return None

        # --- 1. Anti-Fragile Data Check ---
        indicators = {name: self.get_indicator(name) for name in ['vwap_bands', 'atr', 'adx', 'rsi', 'williams_r']}
        if not all([indicators.get('vwap_bands'), indicators.get('atr'), indicators.get('adx')]):
            return None

        # --- ✅ 2. Pillar 1: Market Regime Filter ---
        adx_data = indicators['adx']
        adx_strength = adx_data.get('values', {}).get('adx', 100) # Default to high ADX if data missing
        if adx_strength > cfg.get('max_adx_for_reversion', 25.0):
            logger.debug(f"[{self.strategy_name}] Skipped: Market is trending (ADX: {adx_strength:.2f}). Mean-reversion is disabled.")
            return None

        # --- 3. Primary Trigger: VWAP Band Extension ---
        vwap_data = indicators['vwap_bands']
        vwap_position = vwap_data.get('analysis', {}).get('position')
        signal_direction = None
        if "Below" in vwap_position: signal_direction = "BUY"
        elif "Above" in vwap_position: signal_direction = "SELL"
        else: return None
        
        confirmations = {"trigger": f"Price {vwap_position}", "market_regime": f"Ranging (ADX: {adx_strength:.2f})"}

        # --- 4. Confirmation Funnel ---
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

        # --- 5. Risk Management & Final Checks ---
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

