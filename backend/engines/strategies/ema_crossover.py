# backend/engines/strategies/ema_crossover.py (v6.0 - Trend Command Squad)

import logging
from typing import Dict, Any, Optional, ClassVar, List
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class EmaCrossoverStrategy(BaseStrategy):
    """
    EmaCrossoverStrategy - (v6.0 - Trend Command Squad)
    -------------------------------------------------------------------
    This version evolves the strategy into a "Trend Command Squad," where the
    reliable EMA Cross soldier is supported by a team of specialists. Each
    specialist has a clear mission: scout the battlefield (Regime Filter),
    spot traps (Veto Shields), confirm attack strength (Scoring Engine), and
    plan the exit (Risk Management), all using the robust tools from BaseStrategy.
    """
    strategy_name: str = "EmaCrossoverStrategy"

    default_config: ClassVar[Dict[str, Any]] = {
        # --- Stage 1: Battlefield Selection ---
        "market_regime_filter": {
            "enabled": True,
            "required_regime": "TRENDING",
            "adx_threshold": 21.0
        },
        # --- Stage 3: Defensive Shields ---
        "divergence_veto_enabled": True,
        "exhaustion_shield": {
            "enabled": True,
            "rsi_overbought": 80.0,
            "rsi_oversold": 20.0
        },
        # --- Stage 4: Offensive Squad ---
        "min_confirmation_score": 10,
        "weights": {
            "master_trend": 3,
            "macd": 2,
            "stochastic_cross": 3, # ✅ New Specialist
            "htf_alignment": 2,
            "adx_strength": 1,
            "volume": 1,
            "candlestick": 1
        },
        "stochastic_confirm": {
            "enabled": True,
            "require_strong_cross": True
        },
        "master_trend_filter_enabled": True,
        "macd_confirmation_enabled": True,
        "volume_confirmation_enabled": True,
        "adx_confirmation_enabled": True,
        "min_adx_strength": 20.0,
        "candlestick_confirmation_enabled": True,
        
        # --- Stage 5: Logistics Officers ---
        "master_trend_ma_indicator": "fast_ma",
        "volatility_regimes": { "low_atr_pct_threshold": 1.5, "low_vol_sl_multiplier": 2.0, "high_vol_sl_multiplier": 3.0 },
        "adaptive_targeting": { "enabled": True, "atr_multiples": [2.0, 3.0, 4.0] },

        # --- General ---
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {
            "min_required_score": 1,
            "adx": {"weight": 1, "min_strength": 24},
            "supertrend": {"weight": 1}
        }
    }
    
    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        if not self.price_data:
            self._log_final_decision("HOLD", "No price data available.")
            return None

        # --- Dynamic Data Availability Check ---
        required = ['ema_cross', 'atr', 'adx', 'rsi'] # ADX and RSI are now essential
        if cfg.get('master_trend_filter_enabled'): required.append(cfg.get('master_trend_ma_indicator', 'fast_ma'))
        if cfg.get('macd_confirmation_enabled'): required.append('macd')
        if cfg.get('volume_confirmation_enabled'): required.append('whales')
        if cfg.get('candlestick_confirmation_enabled'): required.append('patterns')
        if cfg.get('divergence_veto_enabled'): required.append('divergence')
        if cfg.get('stochastic_confirm', {}).get('enabled'): required.append('stochastic')
        
        indicators = {name: self.get_indicator(name) for name in set(required)}
        if any(data is None for data in indicators.values()):
            missing = [name for name, data in indicators.items() if data is None]
            self._log_final_decision("HOLD", f"Indicators missing: {', '.join(missing)}"); return None
        
        # --- STAGE 1: BATTLEFIELD SELECTION (Market Regime Filter) ---
        regime_cfg = cfg.get('market_regime_filter', {})
        if regime_cfg.get('enabled', True):
            market_regime, adx_val = self._get_market_regime(adx_threshold=regime_cfg.get('adx_threshold', 22.0))
            required_regime = regime_cfg.get('required_regime', 'TRENDING')
            is_correct_regime = market_regime == required_regime
            self._log_criteria("Market Regime Filter", is_correct_regime, f"Market is '{market_regime}' (ADX={adx_val:.2f}), Required: '{required_regime}'")
            if not is_correct_regime:
                self._log_final_decision("HOLD", f"Incorrect market regime for operation."); return None

        # --- STAGE 2: PRIMARY TRIGGER (EMA Crossover) ---
        primary_signal = self._safe_get(indicators, ['ema_cross', 'analysis', 'signal'])
        if primary_signal not in ["Buy", "Sell"]:
            self._log_final_decision("HOLD", "No primary EMA Cross trigger."); return None
        self._log_criteria("Primary Trigger (EMA Cross)", True, f"Signal: {primary_signal}")
        signal_direction = primary_signal.upper()
        
        # --- STAGE 3: DEFENSIVE SHIELDS (Veto Filters) ---
        # Shield 1: Divergence Veto
        if cfg.get('divergence_veto_enabled', True):
            analysis = self._safe_get(indicators, ['divergence', 'analysis'], {})
            opposing_div = (signal_direction == "BUY" and analysis.get('has_bearish_divergence')) or \
                           (signal_direction == "SELL" and analysis.get('has_bullish_divergence'))
            if opposing_div:
                self._log_criteria("Divergence Veto Shield", False, "Opposing regular divergence detected. VETOED.")
                self._log_final_decision("HOLD", "Vetoed by opposing regular divergence."); return None
        
        # Shield 2: Trend Exhaustion
        exhaustion_cfg = cfg.get('exhaustion_shield', {})
        if exhaustion_cfg.get('enabled', True):
            is_exhausted = self._is_trend_exhausted(
                direction=signal_direction,
                buy_exhaustion_threshold=exhaustion_cfg.get('rsi_overbought', 80.0),
                sell_exhaustion_threshold=exhaustion_cfg.get('rsi_oversold', 20.0)
            )
            if is_exhausted:
                self._log_final_decision("HOLD", "Vetoed by Trend Exhaustion Shield."); return None
        
        self._log_criteria("Defensive Shields", True, "Signal passed all veto filters.")

        # --- STAGE 4: OFFENSIVE SQUAD (Confirmation Scoring) ---
        score = 0; confirmations: List[str] = []; weights = cfg.get('weights', {})

        if cfg.get('master_trend_filter_enabled'):
            ma_val = self._safe_get(indicators, [cfg.get('master_trend_ma_indicator'), 'values', 'ma_value'])
            if self._is_valid_number(self.price_data['close'], ma_val):
                if (signal_direction == "BUY" and self.price_data['close'] > ma_val) or \
                   (signal_direction == "SELL" and self.price_data['close'] < ma_val):
                    score += weights.get('master_trend', 0); confirmations.append("Master Trend")
        
        if cfg.get('macd_confirmation_enabled'):
            histo = self._safe_get(indicators, ['macd', 'values', 'histogram'], 0)
            if (signal_direction == "BUY" and histo > 0) or (signal_direction == "SELL" and histo < 0):
                score += weights.get('macd', 0); confirmations.append("MACD")
        
        # ✅ New Specialist: Stochastic Confirmation
        stoch_cfg = cfg.get('stochastic_confirm', {})
        if stoch_cfg.get('enabled', True):
            stoch_signal = self._safe_get(indicators, ['stochastic', 'analysis', 'crossover_signal'], {})
            is_aligned = stoch_signal.get('direction', '').upper() == signal_direction
            is_strong_enough = not stoch_cfg.get('require_strong_cross', True) or stoch_signal.get('strength') == 'Strong'
            if is_aligned and is_strong_enough:
                score += weights.get('stochastic_cross', 0); confirmations.append("Stochastic Cross")

        if cfg.get('adx_confirmation_enabled'):
            adx_strength = self._safe_get(indicators, ['adx', 'values', 'adx'], 0)
            if adx_strength >= cfg.get('min_adx_strength', 20.0):
                score += weights.get('adx_strength', 0); confirmations.append("ADX Strength")

        if cfg.get('volume_confirmation_enabled'):
            if self._get_volume_confirmation(): score += weights.get('volume', 0); confirmations.append("Volume")

        if cfg.get('htf_confirmation_enabled'):
            if self._get_trend_confirmation(signal_direction): score += weights.get('htf_alignment', 0); confirmations.append("HTF")

        if cfg.get('candlestick_confirmation_enabled'):
            if self._get_candlestick_confirmation(signal_direction): score += weights.get('candlestick', 0); confirmations.append("Candlestick")

        min_score = cfg.get('min_confirmation_score', 8)
        if score < min_score:
            self._log_final_decision("HOLD", f"Confirmation score {score} is below required {min_score}."); return None
        self._log_criteria("Confirmation Score", True, f"Score: {score} >= Min: {min_score}. Confirmed by: {', '.join(confirmations)}")

        # --- STAGE 5: LOGISTICS (Risk Management) ---
        entry_price = self.price_data.get('close')
        long_ema_val = self._safe_get(indicators, ['ema_cross', 'values', 'long_ema'])
        atr_value = self._safe_get(indicators, ['atr', 'values', 'atr'])
        if not self._is_valid_number(entry_price, long_ema_val, atr_value):
            self._log_final_decision("HOLD", "Risk data missing for SL/TP calculation."); return None

        vol_cfg = cfg.get('volatility_regimes', {})
        atr_pct = self._safe_get(indicators, ['atr', 'values', 'atr_percent'], 2.0)
        is_low_vol = atr_pct < vol_cfg.get('low_atr_pct_threshold', 1.5)
        atr_sl_multiplier = vol_cfg.get('low_vol_sl_multiplier', 2.0) if is_low_vol else vol_cfg.get('high_vol_sl_multiplier', 3.0)
        stop_loss = long_ema_val - (atr_value * atr_sl_multiplier) if signal_direction == "BUY" else long_ema_val + (atr_value * atr_sl_multiplier)
        
        # BaseStrategy now handles Adaptive Targeting automatically if this returns no targets
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss=stop_loss)
        
        if not risk_params or not risk_params.get("targets"):
            self._log_final_decision("HOLD", "Failed to generate a valid risk/reward plan."); return None
        
        # --- Final Decision ---
        confirmations_dict = {"score": score, "confirmations_passed": ", ".join(confirmations)}
        self._log_final_decision(signal_direction, f"Trend Command Squad assembled. Score: {score}. Confirmed by: {', '.join(confirmations)}")

        return { "direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations_dict }

