# backend/engines/strategies/ema_crossover.py (v4.1 - Config Safety Fix)

import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class EmaCrossoverStrategy(BaseStrategy):
    """
    EmaCrossoverStrategy - (v4.1 - Config Safety Fix)
    -------------------------------------------------------------------
    This version fixes a critical KeyError caused by an incomplete user config
    for the master_trend_filter. The logic is now hardened to prevent this crash
    and logging has been fully integrated.
    """
    strategy_name: str = "EmaCrossoverStrategy"

    default_config = {
        "default_params": { "min_adx_strength": 23.0, "candlestick_confirmation_enabled": True, },
        "master_trend_filter": { "enabled": True, "ma_indicator": "fast_ma", "ma_period": 200 },
        "strength_engine": { "macd_confirmation_enabled": True, "volume_confirmation_enabled": True },
        "volatility_regimes": { "low_atr_pct_threshold": 1.5, "low_vol_sl_multiplier": 2.0, "high_vol_sl_multiplier": 3.0 },
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": { "min_required_score": 2, "adx": {"weight": 1, "min_strength": 25}, "supertrend": {"weight": 1} }
    }
    
    def _get_signal_config(self) -> Dict[str, Any]:
        final_cfg = self.config.copy()
        base_params = self.config.get("default_params", {})
        tf_overrides = self.config.get("timeframe_overrides", {}).get(self.primary_timeframe, {})
        final_params = {**base_params, **tf_overrides}
        final_cfg.update(final_params)
        return final_cfg

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self._get_signal_config()
        if not self.price_data:
            self._log_final_decision("HOLD", "No price data available.")
            return None

        # --- 1. Dynamic Data Availability Check ---
        required_names = ['ema_cross', 'adx', 'atr']
        trend_cfg = cfg.get('master_trend_filter', {})
        strength_cfg = cfg.get('strength_engine', {})

        if trend_cfg.get('enabled') and trend_cfg.get('ma_indicator'):
            required_names.append(trend_cfg.get('ma_indicator'))
        if strength_cfg.get('macd_confirmation_enabled'):
            required_names.append('macd')
        if strength_cfg.get('volume_confirmation_enabled'):
            required_names.append('whales')
        if cfg.get('candlestick_confirmation_enabled'):
            required_names.append('patterns')
        
        indicators = {name: self.get_indicator(name) for name in list(set(required_names))}
        missing_indicators = [name for name, data in indicators.items() if data is None]
        
        data_is_ok = not missing_indicators
        reason = f"Invalid/Missing indicators: {', '.join(missing_indicators)}" if not data_is_ok else "All required indicator data is valid."
        self._log_criteria("Data Availability", data_is_ok, reason)
        if not data_is_ok:
            self._log_final_decision("HOLD", reason)
            return None

        # --- 2. Primary Trigger (EMA Crossover) ---
        primary_signal = indicators['ema_cross'].get('analysis', {}).get('signal')
        trigger_is_ok = primary_signal in ["Buy", "Sell"]
        self._log_criteria("Primary Trigger (EMA Cross)", trigger_is_ok, f"No valid Buy/Sell signal from EMA Cross. (Signal: {primary_signal})")
        if not trigger_is_ok:
            self._log_final_decision("HOLD", "No primary trigger.")
            return None
        
        signal_direction = primary_signal.upper()
        confirmations = {"entry_trigger": "EMA Cross"}

        # --- 3. Confirmation Funnel ---
        master_trend_ok = True
        if trend_cfg.get('enabled'):
            # ✅ CRITICAL FIX: Safely get the indicator name and then the data.
            ma_indicator_name = trend_cfg.get('ma_indicator')
            if ma_indicator_name and ma_indicator_name in indicators:
                master_ma_data = indicators[ma_indicator_name]
                ma_value = master_ma_data.get('values', {}).get('ma_value')
                if ma_value:
                    master_trend_ok = not ((signal_direction == "BUY" and self.price_data.get('close', 0) < ma_value) or \
                                           (signal_direction == "SELL" and self.price_data.get('close', 0) > ma_value))
                else:
                    master_trend_ok = False # Fail if MA value can't be retrieved
            else:
                master_trend_ok = False # Fail if ma_indicator name is missing in config
        
        self._log_criteria("Pillar 1: Master Trend Filter", master_trend_ok, "Signal is against the long-term Master MA or MA config is invalid.")
        if not master_trend_ok: self._log_final_decision("HOLD", "Master Trend filter failed."); return None
        confirmations['master_trend_filter'] = "Passed"

        # ... (بقیه فانل تایید بدون تغییر باقی می‌ماند) ...
        macd_ok = True
        if strength_cfg.get('macd_confirmation_enabled'):
            histo = indicators['macd'].get('values', {}).get('histogram', 0)
            macd_ok = not ((signal_direction == "BUY" and histo < 0) or (signal_direction == "SELL" and histo > 0))
        self._log_criteria("Pillar 2: MACD Filter", macd_ok, "MACD does not confirm momentum.")
        if not macd_ok: self._log_final_decision("HOLD", "MACD filter failed."); return None
        confirmations['macd_filter'] = "Passed"

        volume_ok = True
        if strength_cfg.get('volume_confirmation_enabled'):
            volume_ok = self._get_volume_confirmation()
        self._log_criteria("Pillar 2: Volume Filter", volume_ok, "No significant volume confirmation.")
        if not volume_ok: self._log_final_decision("HOLD", "Volume filter failed."); return None
        confirmations['volume_filter'] = "Passed"

        adx_ok = indicators['adx'].get('values', {}).get('adx', 0) >= cfg['min_adx_strength']
        self._log_criteria("ADX Filter", adx_ok, f"ADX strength is below threshold. (Value: {indicators['adx'].get('values', {}).get('adx', 0):.2f})")
        if not adx_ok: self._log_final_decision("HOLD", "ADX filter failed."); return None
        confirmations['adx_filter'] = "Passed"

        htf_ok = True
        if cfg['htf_confirmation_enabled']:
            htf_ok = self._get_trend_confirmation(signal_direction)
        self._log_criteria("HTF Filter", htf_ok, "Trend is not aligned with the higher timeframe.")
        if not htf_ok: self._log_final_decision("HOLD", "HTF filter failed."); return None
        confirmations['htf_filter'] = "Passed"
        
        candlestick_ok = True
        if cfg['candlestick_confirmation_enabled']:
            candlestick_ok = self._get_candlestick_confirmation(signal_direction) is not None
        self._log_criteria("Candlestick Filter", candlestick_ok, "No confirming candlestick pattern found.")
        if not candlestick_ok: self._log_final_decision("HOLD", "Candlestick filter failed."); return None
        confirmations['candlestick_filter'] = "Passed"
        
        # --- 4. Dynamic Risk Management ---
        # ... (این بخش بدون تغییر باقی می‌ماند) ...
        entry_price = self.price_data.get('close')
        long_ema_val = indicators['ema_cross'].get('values', {}).get('long_ema')
        atr_value = indicators['atr'].get('values', {}).get('atr')
        
        risk_data_ok = all([entry_price, long_ema_val, atr_value])
        self._log_criteria("Risk Data Availability", risk_data_ok, "Missing data for SL calculation (entry/long_ema/atr).")
        if not risk_data_ok: self._log_final_decision("HOLD", "Risk data missing."); return None

        vol_cfg = cfg.get('volatility_regimes', {})
        atr_pct = indicators['atr'].get('values', {}).get('atr_percent', 2.0)
        is_low_vol = atr_pct < vol_cfg.get('low_atr_pct_threshold', 1.5)
        atr_sl_multiplier = vol_cfg.get('low_vol_sl_multiplier', 2.0) if is_low_vol else vol_cfg.get('high_vol_sl_multiplier', 3.0)
        
        stop_loss = long_ema_val - (atr_value * atr_sl_multiplier) if signal_direction == "BUY" else long_ema_val + (atr_value * atr_sl_multiplier)
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        
        risk_calc_ok = risk_params and risk_params.get("targets")
        self._log_criteria("Risk Calculation", risk_calc_ok, "Smart R/R calculation failed to produce targets.")
        if not risk_calc_ok: self._log_final_decision("HOLD", "Risk parameter calculation failed."); return None
        
        # --- 5. Final Decision ---
        self._log_final_decision(signal_direction, "All criteria met. EMA Crossover signal confirmed.")

        return { "direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations }

