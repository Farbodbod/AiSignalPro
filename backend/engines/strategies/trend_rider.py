# backend/engines/strategies/trend_rider.py - (v8.2 - The Perfected OHRE Integration)

import logging
from typing import Dict, Any, Optional, Tuple, ClassVar
import pandas as pd

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class TrendRiderPro(BaseStrategy):
    """
    TrendRiderPro - (v8.2 - The Perfected OHRE Integration)
    -----------------------------------------------------------------------------------------
    This version perfects the integration with the OHRE engine. Key fixes include:
    1.  **Full Data Provisioning:** The strategy now explicitly requests all necessary
        structural indicators ('structure', 'pivots') to ensure the OHRE can
        leverage its primary, high-conviction plan builders.
    2.  **Configuration Cleanup:** Obsolete risk parameters ('tactical_tp_rr_ratio',
        'min_risk_pct') have been removed from the default_config to align it with
        the strategy's actual logic.
    """
    strategy_name: str = "TrendRiderPro"

    # --- Default config cleaned of obsolete parameters ---
    default_config: ClassVar[Dict[str, Any]] = {
        "market_regime_filter_enabled": True,
        "required_regime": "TRENDING",
        "regime_adx_percentile_threshold": 70.0,
        
        "default_params": {
            "entry_trigger_type": "supertrend", "min_adx_percentile": 70.0,
            "st_multiplier": 3.0, "ch_atr_multiplier": 3.0
        },
        "timeframe_overrides": {
            "5m": { "min_adx_percentile": 65.0 },
            "1d": { "min_adx_percentile": 75.0 }
        },
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {
            "min_required_score": 2, "adx": {"weight": 1, "min_percentile": 75.0}, "supertrend": {"weight": 1}
        }
    }

    # --- Helper methods are unchanged ---
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

    # --- Core logic refactored for full architectural compliance ---
    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self._get_signal_config()
        if not self.price_data: self._log_final_decision("HOLD", "No price data available."); return None

        # --- 1. Data Availability Check (Updated for OHRE) ---
        required_names = ['adx', 'chandelier_exit', 'fast_ma', 'structure', 'pivots']
        if cfg.get('entry_trigger_type') == 'ema_cross': required_names.append('ema_cross')
        else: required_names.append('supertrend')
        
        indicators = {name: self.get_indicator(name) for name in list(set(required_names))}
        missing = [name for name, data in indicators.items() if data is None]
        if missing: self._log_final_decision("HOLD", f"Primary indicators missing: {', '.join(missing)}"); return None
        
        self._log_criteria("Data Availability", True, "All required primary data is valid.")

        # --- 2. Market Regime Filter (Unchanged) ---
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

        # --- 3. Confirmation Funnel (Unchanged) ---
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
        
        # --- 4. Risk Management (UPGRADED to OHRE Engine) ---
        entry_price = self.price_data.get('close')
        
        stop_loss_key = 'long_stop' if signal_direction == "BUY" else 'short_stop'
        sl_anchor_price = self._safe_get(indicators, ['chandelier_exit', 'values', stop_loss_key])

        if not self._is_valid_number(entry_price, sl_anchor_price):
            self._log_final_decision("HOLD", "Risk data missing for OHRE (entry/sl_anchor)."); return None

        risk_params = self._orchestrate_static_risk(
            direction=signal_direction,
            entry_price=entry_price,
            sl_anchor_price=sl_anchor_price
        )

        if not risk_params:
            self._log_final_decision("HOLD", "OHRE failed to generate a valid risk plan."); return None
        
        # --- 5. Final Decision (UPGRADED Narrative) ---
        def _fmt5(x): return f"{float(x):.5f}" if self._is_valid_number(x) else "N/A"
        confirmations = {
            "entry_trigger": entry_trigger_name,
            "strength_filter": f"ADX Percentile > {cfg['min_adx_percentile']:.1f}% (Value: {adx_percentile:.2f}%)",
            "trend_filter": "Price confirmed by Master MA",
            "htf_confirmation": "Confirmed by HTF Engine" if cfg.get('htf_confirmation_enabled') else "Disabled",
            "risk_engine": self.log_details["risk_trace"][-1].get("source", "OHRE"),
            "risk_reward": risk_params.get('risk_reward_ratio'),
            "exit_management": f"SL: {_fmt5(risk_params.get('stop_loss'))}, TP1: {_fmt5(risk_params.get('targets', [None])[0])}"
        }
        self._log_final_decision(signal_direction, "All criteria met. Adaptive Trend Rider signal confirmed by OHRE.")
        
        return {"direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations}

