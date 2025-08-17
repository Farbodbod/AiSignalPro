# backend/engines/strategies/vwap_reversion.py (v5.0 - Peer-Reviewed & Hardened)

from __future__ import annotations
import logging
from typing import Dict, Any, Optional, ClassVar

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class VwapMeanReversion(BaseStrategy):
    """
    VwapMeanReversion - (v5.0 - Peer-Reviewed & Hardened)
    ---------------------------------------------------------------------------
    This version is hardened based on an expert peer review. It includes:
    - Safe float normalization for all numeric inputs (ADX/oscillators).
    - Dynamic and accurate logging messages for all criteria.
    - Robust handling of None, Series, or 0.0 values to prevent crashes.
    - Enhanced type hints and ClassVar for professional code quality.
    """
    strategy_name: str = "VwapMeanReversion"
    default_config: ClassVar[Dict[str, Any]] = {
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

    # ---------- Helpers ----------
    def _get_signal_config(self) -> Dict[str, Any]:
        return self.config

    def _to_float(self, v: Any, default: Optional[float] = 0.0) -> Optional[float]:
        """Safely normalize scalars, arrays, or Series to a single float."""
        try:
            if v is None:
                return default
            if hasattr(v, "__array__") or isinstance(v, (list, tuple)):
                if len(v) == 0:
                    return default
                v = v[-1]
            return float(v)
        except (ValueError, TypeError):
            return default

    def _get_oscillator_confirmation(self, direction: str, cfg: Dict[str, Any], rsi_data: Optional[Dict[str, Any]], wr_data: Optional[Dict[str, Any]]) -> bool:
        rsi_confirm = False
        if cfg.get('use_rsi') and rsi_data:
            rsi_val = self._to_float((rsi_data.get('values') or {}).get('rsi'), default=None)
            if rsi_val is not None:
                if direction == "BUY" and rsi_val < float(cfg['rsi_oversold']): rsi_confirm = True
                elif direction == "SELL" and rsi_val > float(cfg['rsi_overbought']): rsi_confirm = True

        wr_confirm = False
        if cfg.get('use_williams_r') and wr_data:
            wr_val = self._to_float((wr_data.get('values') or {}).get('wr'), default=None)
            if wr_val is not None:
                if direction == "BUY" and wr_val < float(cfg['williams_r_oversold']): wr_confirm = True
                elif direction == "SELL" and wr_val > float(cfg['williams_r_overbought']): wr_confirm = True

        logic = str(cfg.get('oscillator_logic', "AND")).upper()
        if logic == "AND":
            checks = []
            if cfg.get('use_rsi'): checks.append(rsi_confirm)
            if cfg.get('use_williams_r'): checks.append(wr_confirm)
            return all(checks) if checks else False
        elif logic == "OR":
            return rsi_confirm or wr_confirm
        return False

    # ---------- Main Logic ----------
    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self._get_signal_config()
        if not self.price_data:
            self._log_final_decision("HOLD", "No price data available.")
            return None

        # 1) Dynamic & Deep Data Availability
        required_names = ['vwap_bands', 'atr', 'adx']
        if cfg.get('use_rsi'): required_names.append('rsi')
        if cfg.get('use_williams_r'): required_names.append('williams_r')
        if cfg.get('require_candle_confirmation'): required_names.append('patterns')
        
        indicators = {name: self.get_indicator(name) for name in dict.fromkeys(required_names)}
        missing = [name for name, data in indicators.items() if data is None]
        
        if missing:
            reason = f"Invalid/Missing indicators: {', '.join(missing)}"
            self._log_criteria("Data Availability", False, reason)
            self._log_final_decision("HOLD", reason)
            return None
        self._log_criteria("Data Availability", True, "All required indicator data is valid.")

        # 2) Market Regime & Primary Trigger
        adx_strength = self._to_float((indicators['adx'].get('values') or {}).get('adx'), default=100.0)
        max_adx = float(cfg.get('max_adx_for_reversion', 25.0))
        adx_ok = adx_strength <= max_adx
        regime_msg = f"Ranging (ADX={adx_strength:.2f} <= {max_adx:.2f})" if adx_ok else f"Trending (ADX={adx_strength:.2f} > {max_adx:.2f})"
        self._log_criteria("Market Regime (ADX)", adx_ok, regime_msg)
        if not adx_ok:
            self._log_final_decision("HOLD", "ADX filter failed.")
            return None

        vwap_data = indicators['vwap_bands'] or {}
        vwap_position = (vwap_data.get('analysis') or {}).get('position')
        pos_str = str(vwap_position or "").lower()
        signal_direction = "BUY" if "below" in pos_str else ("SELL" if "above" in pos_str else None)
        
        trigger_is_ok = signal_direction is not None
        self._log_criteria("Primary Trigger (VWAP Bands)", trigger_is_ok, f"VWAP position='{pos_str.title()}'")
        if not trigger_is_ok:
            self._log_final_decision("HOLD", "No primary trigger.")
            return None
        confirmations: Dict[str, Any] = {"trigger": f"Price {pos_str.title()}", "market_regime": f"Ranging (ADX: {adx_strength:.2f})"}

        # 3) Confirmation Funnel
        osc_ok = self._get_oscillator_confirmation(signal_direction, cfg, indicators.get('rsi'), indicators.get('williams_r'))
        self._log_criteria("Oscillator Filter", osc_ok, f"Oscillators {'agree' if osc_ok else 'do not agree'} (logic={cfg.get('oscillator_logic')}).")
        if not osc_ok:
            self._log_final_decision("HOLD", "Oscillator filter failed.")
            return None
        confirmations['oscillator_filter'] = f"Passed (Logic: {cfg.get('oscillator_logic')})"
        
        candle_ok = True
        if cfg.get('require_candle_confirmation'):
            candle_ok = self._get_candlestick_confirmation(signal_direction, min_reliability='Medium') is not None
        self._log_criteria("Candlestick Filter", candle_ok, "Confirming candlestick pattern found." if candle_ok else "No confirming pattern found.")
        if not candle_ok:
            self._log_final_decision("HOLD", "Candlestick filter failed.")
            return None
        if cfg.get('require_candle_confirmation'): confirmations['candlestick_filter'] = "Passed"

        htf_ok = True
        if cfg.get('htf_confirmation_enabled'):
            opposite = "SELL" if signal_direction == "BUY" else "BUY"
            htf_ok = not self._get_trend_confirmation(opposite)
        self._log_criteria("HTF Filter", htf_ok, "No strong opposing trend on HTF." if htf_ok else "Strong opposing trend on HTF.")
        if not htf_ok:
            self._log_final_decision("HOLD", "HTF filter failed.")
            return None
        if cfg.get('htf_confirmation_enabled'): confirmations['htf_filter'] = "Passed"
        
        # 4) Risk Management & Target Adjustment
        entry_price = self.price_data.get('close')
        vwap_values = vwap_data.get('values') or {}
        atr_value = self._to_float((indicators['atr'].get('values') or {}).get('atr'), default=None)
        
        if entry_price is None or atr_value is None:
            self._log_final_decision("HOLD", "Risk data missing (entry/atr)."); return None

        stop_loss, sl_source_band = None, None
        atr_mult = float(cfg.get('atr_sl_multiplier', 1.5))
        if signal_direction == "BUY":
            sl_source_band = self._to_float(vwap_values.get('lower_band'))
            if sl_source_band is not None: stop_loss = sl_source_band - (atr_value * atr_mult)
        else: # SELL
            sl_source_band = self._to_float(vwap_values.get('upper_band'))
            if sl_source_band is not None: stop_loss = sl_source_band + (atr_value * atr_mult)

        if stop_loss is None:
            self._log_final_decision("HOLD", "VWAP bands not available for SL calculation."); return None
        
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        if not risk_params:
            self._log_final_decision("HOLD", "Risk engine failed to produce parameters."); return None

        vwap_line = self._to_float(vwap_values.get('vwap'))
        if vwap_line is not None and isinstance(risk_params.get('targets'), list):
            risk_params['targets'] = [vwap_line]
            risk_amount = abs(entry_price - stop_loss)
            if risk_amount > 1e-12:
                risk_params['risk_reward_ratio'] = round(abs(vwap_line - entry_price) / risk_amount, 2)
            self._log_criteria("Target Adjustment", True, "TP adjusted to VWAP line.")

        min_rr = float(cfg.get('min_rr_ratio', 2.0))
        rr_val = (risk_params or {}).get("risk_reward_ratio")
        rr_is_ok = rr_val is not None and rr_val >= min_rr
        
        self._log_criteria("Final R/R Check", rr_is_ok, f"Calculated={rr_val}, Required={min_rr}")
        if not rr_is_ok:
            self._log_final_decision("HOLD", "Final R/R check failed."); return None
        confirmations['rr_check'] = f"Passed (R/R to VWAP: {rr_val})"
        
        # 5) Final Decision
        self._log_final_decision(signal_direction, "All criteria met. VWAP Mean Reversion signal confirmed.")
        
        return { "direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations }
