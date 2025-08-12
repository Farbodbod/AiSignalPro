import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class TrendRiderPro(BaseStrategy):
    """
    TrendRiderPro - (v4.0 - Adaptive Trend Engine)
    -----------------------------------------------------------------------------------------
    This world-class version evolves into a fully adaptive trend engine. It features:
    1.  Timeframe-Aware Intelligence: Utilizes a hierarchical configuration to adapt
        its core parameters (ADX, SuperTrend, Chandelier) to each timeframe.
    2.  Hybrid Exit System: Implements a tactical first take-profit target while
        relying on the Chandelier Exit as a dynamic trailing stop to ride the trend.
    3.  Advanced HTF Confirmation: Fully integrated with the BaseStrategy v4.0's
        weighted, multi-factor HTF confirmation engine.
    """
    strategy_name: str = "TrendRiderPro"

    # ✅ MIRACLE UPGRADE: Hierarchical configuration for timeframe adaptability
    default_config = {
        "default_params": {
            "entry_trigger_type": "supertrend",
            "min_adx_strength": 25.0,
            "st_multiplier": 3.0,
            "ch_atr_multiplier": 3.0,
            "tactical_tp_rr_ratio": 2.0,
            "htf_confirmation_enabled": True
        },
        "timeframe_overrides": {
            "5m": { "min_adx_strength": 22.0, "st_multiplier": 2.5, "ch_atr_multiplier": 2.5 },
            "15m": { "min_adx_strength": 23.0 },
            "1d": { "min_adx_strength": 28.0, "ch_atr_multiplier": 3.5, "tactical_tp_rr_ratio": 2.5 }
        },
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {
            "min_required_score": 2,
            "adx": {"weight": 1, "min_strength": 25},
            "supertrend": {"weight": 1}
        }
    }

    def _get_signal_config(self) -> Dict[str, Any]:
        """ ✅ New: Loads the hierarchical config based on the current timeframe. """
        base_configs = self.config.get("default_params", {})
        tf_overrides = self.config.get("timeframe_overrides", {}).get(self.primary_timeframe, {})
        return {**base_configs, **tf_overrides}

    def _get_primary_signal(self, cfg: Dict[str, Any]) -> tuple[Optional[str], str]:
        # This helper method is enhanced to use adaptive parameters
        if cfg.get('entry_trigger_type') == 'ema_cross':
            # Note: ema periods would also need to be made adaptive if this is a primary trigger
            trigger_name = "EMA Cross"
            ema_cross_data = self.get_indicator('ema_cross')
            if ema_cross_data:
                signal = ema_cross_data.get('analysis', {}).get('signal')
                if signal in ['Buy', 'Sell']: return signal.upper(), trigger_name
        else: # Default to supertrend
            trigger_name = "SuperTrend Crossover"
            supertrend_data = self.get_indicator('supertrend')
            if supertrend_data:
                signal = supertrend_data.get('analysis', {}).get('signal')
                if "Bullish Crossover" in signal: return "BUY", trigger_name
                if "Bearish Crossover" in signal: return "SELL", trigger_name
        return None, ""

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self._get_signal_config()
        if not self.price_data: return None

        # --- 1. Anti-Fragile Data Check ---
        # Dependencies are determined by the configured trigger type
        required_indicators = ['adx', 'chandelier_exit', 'fast_ma']
        if cfg.get('entry_trigger_type') == 'ema_cross':
            required_indicators.append('ema_cross')
        else:
            required_indicators.append('supertrend')
            
        indicators = {name: self.get_indicator(name) for name in required_indicators}
        if not all(indicators.values()): return None

        # --- 2. Get Primary Signal & Run Confirmation Funnel ---
        signal_direction, entry_trigger_name = self._get_primary_signal(cfg)
        if not signal_direction: return None

        # ADX + DMI Filter
        adx_data = indicators['adx']
        adx_strength = adx_data.get('values', {}).get('adx', 0)
        dmi_plus = adx_data.get('values', {}).get('plus_di', 0)
        dmi_minus = adx_data.get('values', {}).get('minus_di', 0)
        if adx_strength < cfg['min_adx_strength']: return None
        if not ((signal_direction == "BUY" and dmi_plus > dmi_minus) or \
                (signal_direction == "SELL" and dmi_minus > dmi_plus)): return None
        
        # Master Trend Filter
        ma_filter_data = indicators['fast_ma']
        ma_value = ma_filter_data.get('values', {}).get('ma_value', 0)
        current_price = self.price_data.get('close', 0)
        if (signal_direction == "BUY" and current_price < ma_value) or \
           (signal_direction == "SELL" and current_price > ma_value):
            return None
        
        # HTF Confirmation (using new weighted engine)
        if cfg['htf_confirmation_enabled']:
            if not self._get_trend_confirmation(signal_direction):
                return None
        
        # --- 3. Hybrid Exit System & Risk Management ---
        entry_price = self.price_data.get('close')
        chandelier_data = indicators['chandelier_exit']
        if not entry_price: return None
        
        stop_loss_key = 'long_stop' if signal_direction == "BUY" else 'short_stop'
        trailing_stop_loss = chandelier_data.get('values', {}).get(stop_loss_key)
        if not trailing_stop_loss: return None

        # We use the Chandelier Exit as the definitive Stop Loss
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, trailing_stop_loss)
        
        # But we create a new Tactical TP1 based on R/R
        risk_amount = abs(entry_price - trailing_stop_loss)
        tactical_tp1 = entry_price + (risk_amount * cfg['tactical_tp_rr_ratio']) if signal_direction == "BUY" else entry_price - (risk_amount * cfg['tactical_tp_rr_ratio'])
        
        # Override the targets from smart risk management with our new hybrid system
        risk_params['targets'] = [round(tactical_tp1, 5)]
        # Recalculate R/R based on this tactical target
        if risk_amount > 1e-9:
             risk_params['risk_reward_ratio'] = round(abs(tactical_tp1 - entry_price) / risk_amount, 2)
        else:
             risk_params['risk_reward_ratio'] = 0

        logger.info(f"✨✨ [{self.strategy_name}] ADAPTIVE TREND RIDER SIGNAL CONFIRMED! ✨✨")
        
        confirmations = {
            "entry_trigger": entry_trigger_name,
            "strength_filter": f"ADX > {cfg['min_adx_strength']} (Value: {adx_strength:.2f})",
            "trend_filter": "Price confirmed by Master MA",
            "htf_confirmation": "Confirmed by HTF Engine" if cfg['htf_confirmation_enabled'] else "Disabled",
            "exit_management": f"Tactical TP1 + Chandelier Trailing SL at {trailing_stop_loss:.5f}"
        }
        
        return {"direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations}

