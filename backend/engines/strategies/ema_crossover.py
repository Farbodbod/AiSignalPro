# backend/engines/strategies/ema_crossover.py (v5.0 - Scoring Engine Upgrade)

import logging
from typing import Dict, Any, Optional, ClassVar, List
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class EmaCrossoverStrategy(BaseStrategy):
    """
    EmaCrossoverStrategy - (v5.0 - Scoring Engine Upgrade)
    -------------------------------------------------------------------
    This version represents a major architectural evolution. The previous
    "all-or-nothing" sequential filter funnel has been replaced with a
    sophisticated weighted "Scoring Engine". Instead of failing on a single
    unmet condition, the strategy now calculates a confirmation score based on
    configurable weights for each pillar (Master Trend, MACD, HTF, etc.).
    This provides immense flexibility and intelligence, transforming the strategy
    from a rigid checklist-follower into an adaptive, high-performance engine.
    """
    strategy_name: str = "EmaCrossoverStrategy"

    default_config: ClassVar[Dict[str, Any]] = {
        # ✅ ARCHITECTURAL UPGRADE (v5.0): New Scoring Engine
        "min_confirmation_score": 6,
        "weights": {
            "master_trend": 3,
            "macd": 2,
            "htf_alignment": 2,
            "adx_strength": 1,
            "volume": 1,
            "candlestick": 1
        },

        # --- Component Settings (used by the scoring engine) ---
        "master_trend_filter_enabled": True,
        "macd_confirmation_enabled": True,
        "volume_confirmation_enabled": True,
        "adx_confirmation_enabled": True,
        "min_adx_strength": 20.0,
        "candlestick_confirmation_enabled": True,
        
        # --- Unchanged Settings ---
        "master_trend_ma_indicator": "fast_ma",
        "volatility_regimes": { "low_atr_pct_threshold": 1.5, "low_vol_sl_multiplier": 2.0, "high_vol_sl_multiplier": 3.0 },
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {
            "min_required_score": 1,
            "adx": {"weight": 1, "min_strength": 22},
            "supertrend": {"weight": 1}
        }
    }
    
    def _get_signal_config(self) -> Dict[str, Any]:
        return self.config.copy()

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self._get_signal_config()
        if not self.price_data:
            self._log_final_decision("HOLD", "No price data available.")
            return None

        # --- 1. Dynamic Data Availability Check ---
        required_names = ['ema_cross', 'atr']
        if cfg.get('master_trend_filter_enabled'): required_names.append(cfg.get('master_trend_ma_indicator', 'fast_ma'))
        if cfg.get('macd_confirmation_enabled'): required_names.append('macd')
        if cfg.get('volume_confirmation_enabled'): required_names.append('whales')
        if cfg.get('adx_confirmation_enabled'): required_names.append('adx')
        if cfg.get('candlestick_confirmation_enabled'): required_names.append('patterns')
        if cfg.get('htf_confirmation_enabled'):
            htf_rules = cfg.get('htf_confirmations', {})
            # ✅ FINAL POLISH (v5.0): Corrected typo hf_rules -> htf_rules
            if "supertrend" in htf_rules: required_names.append('supertrend')
        
        indicators = {name: self.get_indicator(name) for name in list(set(required_names))}
        missing_indicators = [name for name, data in indicators.items() if data is None]
        if missing_indicators:
            self._log_criteria("Data Availability", False, f"Invalid/Missing: {', '.join(missing_indicators)}"); self._log_final_decision("HOLD", "Indicators missing."); return None
        self._log_criteria("Data Availability", True, "All required data is valid.")

        # --- 2. Primary Trigger (EMA Crossover) ---
        primary_signal = (indicators['ema_cross'].get('analysis') or {}).get('signal')
        if primary_signal not in ["Buy", "Sell"]:
            self._log_criteria("Primary Trigger (EMA Cross)", False, f"Signal: {primary_signal}"); self._log_final_decision("HOLD", "No primary trigger."); return None
        self._log_criteria("Primary Trigger (EMA Cross)", True, f"Signal: {primary_signal}")
        signal_direction = primary_signal.upper()
        
        # --- 3. Confirmation Scoring Engine ---
        score = 0; confirmations_passed: List[str] = []; weights = cfg.get('weights', {})

        if cfg.get('master_trend_filter_enabled'):
            master_ma_data = indicators.get(cfg.get('master_trend_ma_indicator'))
            is_ok = False
            if master_ma_data and (ma_value := (master_ma_data.get('values') or {}).get('ma_value')) is not None:
                is_ok = not ((signal_direction == "BUY" and self.price_data['close'] < ma_value) or (signal_direction == "SELL" and self.price_data['close'] > ma_value))
            if is_ok: score += weights.get('master_trend', 0); confirmations_passed.append("Master Trend")
        
        if cfg.get('macd_confirmation_enabled'):
            histo = (indicators.get('macd', {}).get('values') or {}).get('histogram', 0)
            is_ok = not ((signal_direction == "BUY" and histo < 0) or (signal_direction == "SELL" and histo > 0))
            if is_ok: score += weights.get('macd', 0); confirmations_passed.append("MACD")

        if cfg.get('volume_confirmation_enabled'):
            if self._get_volume_confirmation(): score += weights.get('volume', 0); confirmations_passed.append("Volume")
        
        if cfg.get('adx_confirmation_enabled'):
            adx_strength = (indicators.get('adx', {}).get('values') or {}).get('adx', 0)
            if adx_strength >= cfg.get('min_adx_strength', 20.0): score += weights.get('adx_strength', 0); confirmations_passed.append("ADX")

        if cfg.get('htf_confirmation_enabled'):
            if self._get_trend_confirmation(signal_direction): score += weights.get('htf_alignment', 0); confirmations_passed.append("HTF")

        if cfg.get('candlestick_confirmation_enabled'):
            if self._get_candlestick_confirmation(signal_direction) is not None: score += weights.get('candlestick', 0); confirmations_passed.append("Candlestick")

        min_score = cfg.get('min_confirmation_score', 6)
        score_is_ok = score >= min_score
        self._log_criteria("Final Score", score_is_ok, f"Total Score: {score} vs Minimum: {min_score}")
        if not score_is_ok: self._log_final_decision("HOLD", f"Confirmation score {score} is below required {min_score}."); return None

        # --- 4. Dynamic Risk Management ---
        entry_price = self.price_data.get('close')
        long_ema_val = (indicators['ema_cross'].get('values') or {}).get('long_ema')
        atr_value = (indicators['atr'].get('values') or {}).get('atr')
        if not all(v is not None for v in [entry_price, long_ema_val, atr_value]):
            self._log_final_decision("HOLD", "Risk data missing."); return None

        vol_cfg = cfg.get('volatility_regimes', {})
        atr_pct = (indicators['atr'].get('values') or {}).get('atr_percent', 2.0)
        is_low_vol = atr_pct < vol_cfg.get('low_atr_pct_threshold', 1.5)
        atr_sl_multiplier = vol_cfg.get('low_vol_sl_multiplier', 2.0) if is_low_vol else vol_cfg.get('high_vol_sl_multiplier', 3.0)
        stop_loss = long_ema_val - (atr_value * atr_sl_multiplier) if signal_direction == "BUY" else long_ema_val + (atr_value * atr_sl_multiplier)
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        
        if not (risk_params and risk_params.get("targets")):
            self._log_final_decision("HOLD", "Risk calculation failed."); return None
        
        # --- 5. Final Decision ---
        confirmations = {"score": score, "confirmations_passed": ", ".join(confirmations_passed)}
        self._log_final_decision(signal_direction, "All criteria met. EMA Crossover signal confirmed.")

        return { "direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations }

