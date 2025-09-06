# backend/engines/strategies/vwap_reversion.py (v7.1 - The Robust Risk Engine)

from __future__ import annotations
import logging
from typing import Dict, Any, Optional, ClassVar, List, Tuple

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class VwapMeanReversion(BaseStrategy):
    """
    VwapMeanReversion - (v7.1 - The Robust Risk Engine)
    ---------------------------------------------------------------------------
    This version contains a critical hotfix to its risk management engine. The
    fragile stop-loss logic, based on VWAP bands, has been replaced with a robust
    method anchored to the signal candle's price action (High/Low) and ATR.
    This eliminates unrealistic R/R ratios and makes the strategy viable for
    production use.
    """
    strategy_name: str = "VwapMeanReversion"
    default_config: ClassVar[Dict[str, Any]] = {
        "max_adx_for_reversion": 22.0,
        "min_rr_ratio": 1.5,
        "oscillator_logic": "OR",
        "use_rsi": True, "rsi_oversold": 30.0, "rsi_overbought": 70.0,
        "use_williams_r": True, "williams_r_oversold": -80.0, "williams_r_overbought": -20.0,
        "atr_sl_multiplier": 1.2,
        "require_candle_confirmation": True,
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {
            "min_required_score": 1,
            "adx": {"weight": 1, "min_strength": 25}
        }
    }

    # ---------- Helpers (Unchanged) ----------
    def _get_signal_config(self) -> Dict[str, Any]:
        return self.config

    def _to_float(self, v: Any, default: Optional[float] = None) -> Optional[float]:
        if v is None: return default
        try: return float(v)
        except (ValueError, TypeError): return default

    def _get_latest_value(self, v: Any) -> Any:
        if hasattr(v, 'iloc'): return v.iloc[-1] if not v.empty else None
        if isinstance(v, (list, tuple)): return v[-1] if v else None
        return v

    def _get_oscillator_confirmation(self, direction: str, cfg: Dict[str, Any], rsi_data: Optional[Dict[str, Any]], wr_data: Optional[Dict[str, Any]]) -> bool:
        # ... [This method is unchanged and correct] ...
        rsi_confirm = False
        if cfg.get('use_rsi') and rsi_data:
            rsi_val = self._to_float(self._get_latest_value((rsi_data.get('values') or {}).get('rsi')), default=None)
            if rsi_val is not None:
                if direction == "BUY" and rsi_val < float(cfg['rsi_oversold']): rsi_confirm = True
                elif direction == "SELL" and rsi_val > float(cfg['rsi_overbought']): rsi_confirm = True
        
        wr_confirm = False
        if cfg.get('use_williams_r') and wr_data:
            wr_val = self._to_float(self._get_latest_value((wr_data.get('values') or {}).get('wr')), default=None)
            if wr_val is not None:
                if direction == "BUY" and wr_val < float(cfg['williams_r_oversold']): wr_confirm = True
                elif direction == "SELL" and wr_val > float(cfg['williams_r_overbought']): wr_confirm = True
        
        logic = str(cfg.get('oscillator_logic', "AND")).upper()
        if logic == "AND":
            checks = []
            if cfg.get('use_rsi'): checks.append(rsi_confirm)
            if cfg.get('use_williams_r'): checks.append(wr_confirm)
            return all(checks) if checks else False
        elif logic == "OR": return rsi_confirm or wr_confirm
        return False

    # ---------- Main Logic ----------
    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self._get_signal_config()
        if not self.price_data:
            self._log_final_decision("HOLD", "No price data available.")
            return None

        # --- 1. Data Availability (Unchanged) ---
        required_names = ['vwap_bands', 'atr', 'adx']
        if cfg.get('use_rsi'): required_names.append('rsi')
        if cfg.get('use_williams_r'): required_names.append('williams_r')
        if cfg.get('require_candle_confirmation'): required_names.append('patterns')
        indicators = {name: self.get_indicator(name) for name in dict.fromkeys(required_names)}
        missing = [name for name, data in indicators.items() if not data or 'values' not in data]
        if missing:
            reason = f"Invalid/Missing indicators (or 'values' key): {', '.join(missing)}"
            self._log_criteria("Data Availability", False, reason); self._log_final_decision("HOLD", reason)
            return None
        self._log_criteria("Data Availability", True, "All required indicator data is valid and complete.")

        # --- 2. Market Regime & Primary Trigger (Unchanged) ---
        adx_raw_value = (indicators['adx'].get('values') or {}).get('adx'); adx_strength = self._to_float(self._get_latest_value(adx_raw_value), default=None)
        if adx_strength is None:
            self._log_criteria("Market Regime (ADX)", False, "ADX value could not be parsed."); self._log_final_decision("HOLD", "ADX data was not available.")
            return None
        max_adx = float(cfg.get('max_adx_for_reversion', 25.0)); adx_ok = adx_strength <= max_adx
        regime_msg = f"Ranging (ADX={adx_strength:.2f} <= {max_adx:.2f})" if adx_ok else f"Trending (ADX={adx_strength:.2f} > {max_adx:.2f})"
        self._log_criteria("Market Regime (ADX)", adx_ok, regime_msg)
        if not adx_ok: self._log_final_decision("HOLD", f"ADX filter failed. {regime_msg}"); return None
        
        vwap_data = indicators['vwap_bands']; vwap_position = (vwap_data.get('analysis') or {}).get('position'); pos_str = str(vwap_position or "").lower()
        signal_direction = "BUY" if "below" in pos_str else ("SELL" if "above" in pos_str else None)
        trigger_is_ok = signal_direction is not None
        self._log_criteria("Primary Trigger (VWAP Bands)", trigger_is_ok, f"VWAP position='{pos_str.title()}'")
        if not trigger_is_ok: self._log_final_decision("HOLD", "No primary trigger."); return None
        confirmations: Dict[str, Any] = {"trigger": f"Price {pos_str.title()}", "market_regime": f"Ranging (ADX: {adx_strength:.2f})"}

        # --- 3. Confirmation Funnel (Unchanged) ---
        osc_ok = self._get_oscillator_confirmation(signal_direction, cfg, indicators.get('rsi'), indicators.get('williams_r'))
        self._log_criteria("Oscillator Filter", osc_ok, f"Oscillators {'agree' if osc_ok else 'do not agree'} (logic={cfg.get('oscillator_logic')}).")
        if not osc_ok: self._log_final_decision("HOLD", "Oscillator filter failed."); return None
        confirmations['oscillator_filter'] = f"Passed (Logic: {cfg.get('oscillator_logic')})"
        
        candle_ok = True
        if cfg.get('require_candle_confirmation'): candle_ok = self._get_candlestick_confirmation(signal_direction, min_reliability='Medium') is not None
        self._log_criteria("Candlestick Filter", candle_ok, "Confirming candlestick pattern found." if candle_ok else "No confirming pattern found.")
        if not candle_ok: self._log_final_decision("HOLD", "Candlestick filter failed."); return None
        if cfg.get('require_candle_confirmation'): confirmations['candlestick_filter'] = "Passed"

        htf_ok = True
        if cfg.get('htf_confirmation_enabled'):
            opposite = "SELL" if signal_direction == "BUY" else "BUY"; htf_ok = not self._get_trend_confirmation(opposite)
        self._log_criteria("HTF Filter", htf_ok, "No strong opposing trend on HTF." if htf_ok else "Strong opposing trend on HTF.")
        if not htf_ok: self._log_final_decision("HOLD", "HTF filter failed."); return None
        if cfg.get('htf_confirmation_enabled'): confirmations['htf_filter'] = "Passed"
        
        # --- 4. Risk Management & Target Adjustment ---
        entry_price = self.price_data.get('close')
        atr_raw_value = (indicators['atr'].get('values') or {}).get('atr')
        atr_value = self._to_float(self._get_latest_value(atr_raw_value), default=None)
        if entry_price is None or atr_value is None:
            self._log_final_decision("HOLD", "Risk data missing (entry/atr)."); return None

        # ✅ ROBUST RISK ENGINE (v7.1): Re-engineered Stop Loss logic.
        # The old logic based on the VWAP band was fragile and could create unrealistic R/R.
        # The new logic anchors the SL to the signal candle's price action for stability.
        stop_loss: Optional[float] = None
        atr_mult = float(cfg.get('atr_sl_multiplier', 1.5))
        
        if signal_direction == "BUY":
            signal_candle_low = self.price_data.get('low')
            if signal_candle_low is not None:
                stop_loss = signal_candle_low - (atr_value * atr_mult)
        else: # SELL
            signal_candle_high = self.price_data.get('high')
            if signal_candle_high is not None:
                stop_loss = signal_candle_high + (atr_value * atr_mult)

        if stop_loss is None:
            self._log_final_decision("HOLD", "Could not determine SL from signal candle price data.")
            return None
        
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        if not risk_params: self._log_final_decision("HOLD", "Risk engine failed to produce parameters."); return None

        vwap_values = indicators['vwap_bands'].get('values') or {}
        vwap_line = self._to_float(self._get_latest_value(vwap_values.get('vwap')))
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
        if not rr_is_ok: self._log_final_decision("HOLD", "Final R/R check failed."); return None
        confirmations['rr_check'] = f"Passed (R/R to VWAP: {rr_val})"
        
        # --- 5. Final Decision ---
        self._log_final_decision(signal_direction, "All criteria met. VWAP Mean Reversion signal confirmed.")
        
        return { "direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations }

