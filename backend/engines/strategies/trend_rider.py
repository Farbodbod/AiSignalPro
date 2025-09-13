# backend/engines/strategies/trend_rider.py - (v10.2 - The Polished Rider)

import logging
from typing import Dict, Any, Optional, Tuple, ClassVar

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class TrendRiderPro(BaseStrategy):
    """
    TrendRiderPro - (v10.2 - The Polished Rider)
    -----------------------------------------------------------------------------------------
    This version applies the "Grandmaster's Final Polish" based on live signal
    analysis. It integrates an internal, dynamic Exhaustion Shield to filter out
    overextended entries and enforces a higher, strategy-specific minimum R/R
    to align with its trend-riding philosophy, resulting in fewer but higher-
    quality trading opportunities.
    """
    strategy_name: str = "TrendRiderPro"

    default_config: ClassVar[Dict[str, Any]] = {
        "market_regime_filter_enabled": True,
        "required_regime": "TRENDING",
        "regime_adx_percentile_threshold": 65.0,
        
        "default_params": {
            "entry_trigger_type": "supertrend", 
            "min_adx_percentile": 55.0,
        },
        "timeframe_overrides": {
            "5m": { "min_adx_percentile": 50.0 },
            "1d": { "min_adx_percentile": 60.0 }
        },
        
        # ✅ POLISH 1: Exhaustion Shield Configuration
        "exhaustion_shield": {
            "enabled": True,
            "rsi_lookback": 120,
            "rsi_buy_percentile": 85,
            "rsi_sell_percentile": 15
        },
        
        # ✅ POLISH 2: Sniper's R/R Standard
        "min_rr_ratio": 1.8,
        
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {
            "min_required_score": 2, 
            "adx": {"weight": 1, "min_percentile": 70.0},
            "supertrend": {"weight": 1}
        }
    }

    # --- Helper methods ---
    def _get_signal_config(self) -> Dict[str, Any]:
        final_cfg = self.config.copy()
        base_params = self.config.get("default_params", {})
        tf_overrides = self.config.get("timeframe_overrides", {}).get(self.primary_timeframe, {})
        final_params = {**base_params, **tf_overrides}
        final_cfg.update(final_params)
        return final_cfg

    def _get_primary_signal(self, cfg: Dict[str, Any]) -> Tuple[Optional[str], str]:
        # This state-driven logic is preserved from v10.1
        trigger_name = "SuperTrend Continuation"
        supertrend_data = self.get_indicator('supertrend')
        if not supertrend_data or 'analysis' not in supertrend_data: return None, ""
        analysis = supertrend_data['analysis']
        trend_direction, signal = analysis.get('trend'), analysis.get('signal')
        if signal == 'Trend Continuation':
            if trend_direction == 'Uptrend': return "BUY", trigger_name
            if trend_direction == 'Downtrend': return "SELL", trigger_name
        signal_text = str(signal).lower()
        if "bullish crossover" in signal_text: return "BUY", "SuperTrend Crossover"
        if "bearish crossover" in signal_text: return "SELL", "SuperTrend Crossover"
        return None, ""

    def _fmt5(self, x: Any) -> str:
        return f"{float(x):.5f}" if self._is_valid_number(x) else "N/A"

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self._get_signal_config()
        if not self.price_data: self._log_final_decision("HOLD", "No price data available."); return None

        # ✅ Added 'rsi' for the new Exhaustion Shield
        required_names = ['adx', 'fast_ma', 'structure', 'pivots', 'supertrend', 'rsi']
        
        indicators = {name: self.get_indicator(name) for name in list(set(required_names))}
        missing = [name for name, data in indicators.items() if data is None]
        if missing: self._log_final_decision("HOLD", f"Primary indicators missing: {', '.join(missing)}"); return None
        
        self._log_criteria("Data Availability", True, "All required primary data is valid.")

        # --- Market Regime & Confirmation Funnel (Unchanged) ---
        if cfg.get('market_regime_filter_enabled'):
            required_regime = cfg.get('required_regime', 'TRENDING')
            adx_percentile = self._safe_get(indicators.get('adx'), ['analysis', 'adx_percentile'], 0.0)
            percentile_threshold = float(cfg.get('regime_adx_percentile_threshold', 65.0))
            market_regime = "TRENDING" if adx_percentile >= percentile_threshold else "RANGING"
            if market_regime != required_regime:
                self._log_final_decision("HOLD", "Market regime not suitable."); return None
        
        signal_direction, entry_trigger_name = self._get_primary_signal(cfg)
        if not signal_direction: self._log_final_decision("HOLD", "No primary trigger."); return None
        self._log_criteria(f"Primary Trigger ({entry_trigger_name})", True, f"Signal found: {signal_direction}")

        adx_percentile = self._safe_get(indicators.get('adx'), ['analysis', 'adx_percentile'], 0.0)
        dmi_plus = self._safe_get(indicators.get('adx'), ['values', 'plus_di'], 0.0)
        dmi_minus = self._safe_get(indicators.get('adx'), ['values', 'minus_di'], 0.0)
        is_trend_strong = adx_percentile >= cfg['min_adx_percentile']
        is_dir_confirmed = (signal_direction == "BUY" and dmi_plus > dmi_minus) or (signal_direction == "SELL" and dmi_minus > dmi_plus)
        if not (is_trend_strong and is_dir_confirmed): self._log_final_decision("HOLD", "ADX/DMI filter failed."); return None
        
        current_price = self.price_data.get('close')
        ma_value = self._safe_get(indicators.get('fast_ma'), ['values', 'ma_value'])
        ma_filter_ok = not ((signal_direction == "BUY" and current_price < ma_value) or (signal_direction == "SELL" and current_price > ma_value))
        if not ma_filter_ok: self._log_final_decision("HOLD", "Master Trend filter failed."); return None
        
        htf_ok = self._get_trend_confirmation(signal_direction) if cfg.get('htf_confirmation_enabled') else True
        if not htf_ok: self._log_final_decision("HOLD", "HTF filter failed."); return None

        # ✅ POLISH 1: Internal Exhaustion Shield
        shield_cfg = cfg.get('exhaustion_shield', {})
        if shield_cfg.get('enabled', True):
            if self._is_trend_exhausted_dynamic(
                direction=signal_direction,
                rsi_lookback=shield_cfg.get('rsi_lookback', 120),
                rsi_buy_percentile=shield_cfg.get('rsi_buy_percentile', 85),
                rsi_sell_percentile=shield_cfg.get('rsi_sell_percentile', 15)
            ):
                self._log_criteria("Exhaustion Shield", False, "Signal vetoed internally by dynamic RSI.")
                self._log_final_decision("HOLD", "Signal vetoed by internal Exhaustion Shield.")
                return None
        self._log_criteria("Internal Veto Shields", True, "Signal passed all internal checks.")
        
        # --- Risk Management (Now with higher R/R standard) ---
        entry_price = self.price_data.get('close')
        
        # ✅ POLISH 2: Enforce the higher R/R standard via override
        min_rr_needed = cfg.get('min_rr_ratio', 1.8)
        self.config['override_min_rr_ratio'] = min_rr_needed
        
        risk_params = self._orchestrate_static_risk(
            direction=signal_direction,
            entry_price=entry_price
        )
        
        self.config.pop('override_min_rr_ratio', None) # Clean up

        if not risk_params:
            self._log_final_decision("HOLD", f"OHRE v3.0 failed to generate a valid risk plan (min R:R needed: {min_rr_needed}).")
            return None
        
        # --- Final Decision ---
        confirmations = {
            "entry_trigger": entry_trigger_name,
            "strength_filter": f"ADX Percentile > {cfg['min_adx_percentile']:.1f}% (Value: {adx_percentile:.2f}%)",
            "trend_filter": "Price confirmed by Master MA",
            "htf_confirmation": "Confirmed by HTF Engine",
            "risk_engine": self.log_details["risk_trace"][-1].get("source", "OHRE v3.0"),
            "risk_reward": risk_params.get('risk_reward_ratio'),
            "exit_management": f"SL: {self._fmt5(risk_params.get('stop_loss'))}, TP1: {self._fmt5(risk_params.get('targets', [None])[0])}"
        }
        self._log_final_decision(signal_direction, "All criteria met. Trend Rider signal polished and confirmed.")
        
        return {"direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations}
