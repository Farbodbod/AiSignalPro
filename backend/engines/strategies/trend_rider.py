#backend/engines/strategies/trend_rider.py - (v8.0 - The Adaptive Engine Integration)

import logging
from typing import Dict, Any, Optional, Tuple, ClassVar
import pandas as pd

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class TrendRiderPro(BaseStrategy):
    """
    TrendRiderPro - (v8.0 - The Adaptive Engine Integration)
    -----------------------------------------------------------------------------------------
    This major upgrade fully integrates the Adaptive Regime Engine (ADX v6.0). All
    fixed ADX thresholds for market regime filtering, primary signal confirmation, and
    HTF confirmation have been replaced with adaptive percentile-based logic. This
    makes the strategy significantly more context-aware and robust across different
    market conditions and assets.
    """
    strategy_name: str = "TrendRiderPro"

    default_config: ClassVar[Dict[str, Any]] = {
        # ✅ UPGRADED: Context Filters now use adaptive percentiles
        "market_regime_filter_enabled": True,
        "required_regime": "TRENDING",
        "regime_adx_percentile_threshold": 70.0,
        
        # ✅ UPGRADED: Core Logic now uses adaptive percentiles
        "default_params": {
            "entry_trigger_type": "supertrend", "min_adx_percentile": 70.0,
            "st_multiplier": 3.0, "ch_atr_multiplier": 3.0, "tactical_tp_rr_ratio": 2.0,
            "min_risk_pct": 0.1
        },
        "timeframe_overrides": {
            "5m": { "min_adx_percentile": 65.0 },
            "1d": { "min_adx_percentile": 75.0, "tactical_tp_rr_ratio": 2.5 }
        },
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        # ✅ UPGRADED: HTF confirmations config now uses adaptive percentiles
        "htf_confirmations": {
            "min_required_score": 2, "adx": {"weight": 1, "min_percentile": 75.0}, "supertrend": {"weight": 1}
        }
    }

    def _get_signal_config(self) -> Dict[str, Any]:
        final_cfg = self.config.copy()
        base_params = self.config.get("default_params", {})
        tf_overrides = self.config.get("timeframe_overrides", {}).get(self.primary_timeframe, {})
        final_params = {**base_params, **tf_overrides}
        final_cfg.update(final_params)
        return final_cfg

    def _get_primary_signal(self, cfg: Dict[str, Any]) -> Tuple[Optional[str], str]:
        if cfg.get('entry_trigger_type') == 'ema_cross':
            trigger_name = "EMA Cross"; ema_cross_data = self.get_indicator('ema_cross')
            if ema_cross_data:
                signal = (ema_cross_data.get('analysis') or {}).get('signal')
                if signal in ['Buy', 'Sell']: return signal.upper(), trigger_name
        else: # Default to supertrend
            trigger_name = "SuperTrend Crossover"; supertrend_data = self.get_indicator('supertrend')
            if supertrend_data:
                signal = str((supertrend_data.get('analysis') or {}).get('signal', '')).lower()
                if "bullish crossover" in signal: return "BUY", trigger_name
                if "bearish crossover" in signal: return "SELL", trigger_name
        return None, ""

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self._get_signal_config()
        if not self.price_data: self._log_final_decision("HOLD", "No price data available."); return None

        # --- 1. Data Availability Check (Unchanged) ---
        required_names = ['adx', 'chandelier_exit', 'fast_ma']
        if cfg.get('entry_trigger_type') == 'ema_cross': required_names.append('ema_cross')
        else: required_names.append('supertrend')
        
        indicators = {name: self.get_indicator(name) for name in list(set(required_names))}
        missing = [name for name, data in indicators.items() if data is None]
        if missing: self._log_final_decision("HOLD", f"Indicators missing: {', '.join(missing)}"); return None
        
        if cfg.get('htf_confirmation_enabled'):
            htf_rules = cfg.get('htf_confirmations', {})
            htf_required = [name for name in htf_rules if name != 'min_required_score']
            htf_indicators = {name: self.get_indicator(name, analysis_source=self.htf_analysis) for name in htf_required}
            htf_missing = [name for name, data in htf_indicators.items() if data is None]
            if htf_missing: self._log_final_decision("HOLD", f"HTF indicators missing: {', '.join(htf_missing)}"); return None
        
        self._log_criteria("Data Availability", True, "All required primary and HTF data is valid.")

        # --- 2. Market Regime Filter (✅ UPGRADED) ---
        if cfg.get('market_regime_filter_enabled'):
            required_regime = cfg.get('required_regime', 'TRENDING')
            adx_data = indicators.get('adx')
            adx_percentile = self._safe_get(adx_data, ['analysis', 'adx_percentile'], 0.0)
            percentile_threshold = float(cfg.get('regime_adx_percentile_threshold', 70.0))
            
            market_regime = "TRENDING" if adx_percentile >= percentile_threshold else "RANGING"
            regime_is_ok = (market_regime == required_regime)
            
            reason = f"Market is '{market_regime}' (ADX Percentile={adx_percentile:.2f}%), but strategy requires '{required_regime}'."
            self._log_criteria("Market Regime Filter (Adaptive)", regime_is_ok, reason)
            if not regime_is_ok: self._log_final_decision("HOLD", "Market regime is not suitable."); return None

        # --- 3. Confirmation Funnel (✅ UPGRADED) ---
        signal_direction, entry_trigger_name = self._get_primary_signal(cfg)
        self._log_criteria("Primary Trigger", signal_direction is not None, f"Signal from {cfg.get('entry_trigger_type')}: {'Found' if signal_direction else 'Not Found'}")
        if not signal_direction: self._log_final_decision("HOLD", "No primary trigger."); return None

        adx_percentile = self._safe_get(indicators.get('adx'), ['analysis', 'adx_percentile'], 0.0)
        dmi_plus = self._safe_get(indicators.get('adx'), ['values', 'plus_di'], 0.0)
        dmi_minus = self._safe_get(indicators.get('adx'), ['values', 'minus_di'], 0.0)

        is_trend_strong = adx_percentile >= cfg['min_adx_percentile']
        is_dir_confirmed = (signal_direction == "BUY" and dmi_plus > dmi_minus) or (signal_direction == "SELL" and dmi_minus > dmi_plus)
        adx_ok = is_trend_strong and is_dir_confirmed
        self._log_criteria("ADX/DMI Filter (Adaptive)", adx_ok, f"Trend strong/aligned check. (ADX Percentile: {adx_percentile:.2f}%)")
        if not adx_ok: self._log_final_decision("HOLD", "ADX/DMI filter failed."); return None
        
        current_price = self.price_data.get('close')
        ma_value = self._safe_get(indicators.get('fast_ma'), ['values', 'ma_value'])
        ma_filter_ok = True
        if self._is_valid_number(current_price, ma_value):
            ma_filter_ok = not ((signal_direction == "BUY" and current_price < ma_value) or (signal_direction == "SELL" and current_price > ma_value))
        else: ma_filter_ok = False
        self._log_criteria("Master Trend Filter", ma_filter_ok, "Price is on the wrong side of the master MA.")
        if not ma_filter_ok: self._log_final_decision("HOLD", "Master Trend filter failed."); return None
        
        htf_ok = True
        if cfg.get('htf_confirmation_enabled'): htf_ok = self._get_trend_confirmation(signal_direction)
        self._log_criteria("HTF Filter", htf_ok, "Not aligned with HTF." if not htf_ok else "HTF is aligned.")
        if not htf_ok: self._log_final_decision("HOLD", "HTF filter failed."); return None
        
        # --- 4. Risk Management (Unchanged) ---
        entry_price = self.price_data.get('close')
        stop_loss_key = 'long_stop' if signal_direction == "BUY" else 'short_stop'
        trailing_stop_loss = (indicators['chandelier_exit'].get('values') or {}).get(stop_loss_key)

        if not self._is_valid_number(entry_price, trailing_stop_loss):
            self._log_final_decision("HOLD", "Risk data missing or invalid (entry/SL)."); return None

        risk_amount = abs(entry_price - trailing_stop_loss)
        min_risk_threshold = entry_price * (cfg.get('min_risk_pct', 0.1) / 100)
        if risk_amount < min_risk_threshold:
            self._log_final_decision("HOLD", f"Risk too tight ({risk_amount:.4f} < {min_risk_threshold:.4f})."); return None
        
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, trailing_stop_loss)
        tactical_tp1 = entry_price + (risk_amount * cfg['tactical_tp_rr_ratio']) if signal_direction == "BUY" else entry_price - (risk_amount * cfg['tactical_tp_rr_ratio'])
        
        if not isinstance(risk_params, dict): risk_params = {}
            
        risk_params['targets'] = [round(tactical_tp1, 5)]
        risk_params['risk_reward_ratio'] = round(abs(tactical_tp1 - entry_price) / risk_amount, 2) if risk_amount > 1e-9 else 0
        
        # --- 5. Final Decision (✅ UPGRADED Narrative) ---
        def _fmt5(x): return f"{float(x):.5f}" if self._is_valid_number(x) else "N/A"
        confirmations = {
            "entry_trigger": entry_trigger_name,
            "strength_filter": f"ADX Percentile > {cfg['min_adx_percentile']:.1f}% (Value: {adx_percentile:.2f}%)",
            "trend_filter": "Price confirmed by Master MA",
            "htf_confirmation": "Confirmed by HTF Engine" if cfg.get('htf_confirmation_enabled') else "Disabled",
            "exit_management": f"Tactical TP1 + Chandelier Trailing SL at {_fmt5(trailing_stop_loss)}"
        }
        self._log_final_decision(signal_direction, "All criteria met. Adaptive Trend Rider signal confirmed.")
        
        return {"direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations}
