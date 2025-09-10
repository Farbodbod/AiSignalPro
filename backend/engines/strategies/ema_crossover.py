# backend/engines/strategies/Ema_Crossover.py - (v7.2 - The Perfected OHRE Integration)

import logging
from typing import Dict, Any, Optional, ClassVar, List
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class EmaCrossoverStrategy(BaseStrategy):
    """
    EmaCrossoverStrategy - (v7.2 - The Perfected OHRE Integration)
    -------------------------------------------------------------------
    This version perfects the integration with the OHRE engine. Key fixes include:
    1.  **Full Data Provisioning:** The strategy now explicitly requests all necessary
        structural indicators ('structure', 'pivots') to ensure the OHRE can
        leverage its primary, high-conviction plan builders instead of defaulting
        to its fallback mechanism.
    2.  **Configuration Cleanup:** The obsolete 'adaptive_targeting' parameter has been
        removed from the default_config to eliminate confusion and align the
        internal configuration with the strategy's actual logic.
    """
    strategy_name: str = "EmaCrossoverStrategy"

    # --- Default config cleaned of obsolete parameters ---
    default_config: ClassVar[Dict[str, Any]] = {
        "market_regime_filter": {
            "enabled": True, "required_regime": "TRENDING", "adx_percentile_threshold": 70.0
        },
        "exhaustion_shield": {
            "enabled": True, "mode": "dynamic", "dynamic_rsi_lookback": 120,
            "dynamic_overbought_percentile": 85, "dynamic_oversold_percentile": 15
        },
        "divergence_veto_enabled": False,
        "min_confirmation_score": 12,
        "weights": {
            "master_trend": 4, "hidden_divergence": 4, "macd": 3, "adx_strength": 3,
            "stochastic_cross": 2, "volume": 2, "htf_alignment": 2, "candlestick": 1
        },
        "stochastic_confirm": {"enabled": True, "require_strong_cross": True},
        "master_trend_filter_enabled": True,
        "macd_confirmation_enabled": True,
        "volume_confirmation_enabled": True,
        "adx_confirmation_enabled": True,
        "min_adx_percentile": 70.0,
        "candlestick_confirmation_enabled": True,
        "master_trend_ma_indicator": "fast_ma",
        "volatility_regimes": { "low_atr_pct_threshold": 1.5, "low_vol_sl_multiplier": 2.0, "high_vol_sl_multiplier": 3.0 },
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {
            "min_required_score": 1,
            "adx": {"weight": 1, "min_percentile": 75.0},
            "supertrend": {"weight": 1}
        }
    }
    
    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        if not self.price_data:
            self._log_final_decision("HOLD", "No price data available."); return None

        # --- Indicator requirements updated to feed the OHRE engine ---
        required = ['ema_cross', 'atr', 'adx', 'rsi', 'divergence', 'structure', 'pivots']
        if cfg.get('master_trend_filter_enabled'): required.append(cfg.get('master_trend_ma_indicator', 'fast_ma'))
        if cfg.get('macd_confirmation_enabled'): required.append('macd')
        if cfg.get('volume_confirmation_enabled'): required.append('whales')
        if cfg.get('candlestick_confirmation_enabled'): required.append('patterns')
        if cfg.get('stochastic_confirm', {}).get('enabled'): required.append('stochastic')
        
        indicators = {name: self.get_indicator(name) for name in set(required)}
        if any(data is None for data in indicators.values()):
            missing = [name for name, data in indicators.items() if data is None]
            self._log_final_decision("HOLD", f"Indicators missing: {', '.join(missing)}"); return None
        
        # --- STAGES 1-4 remain unchanged ---
        # STAGE 1: BATTLEFIELD SELECTION
        regime_cfg = cfg.get('market_regime_filter', {})
        if regime_cfg.get('enabled', True):
            adx_percentile = self._safe_get(indicators.get('adx'), ['analysis', 'adx_percentile'], 0.0)
            percentile_threshold = regime_cfg.get('adx_percentile_threshold', 70.0)
            market_regime = "TRENDING" if adx_percentile >= percentile_threshold else "RANGING"
            required_regime = regime_cfg.get('required_regime', 'TRENDING')
            is_correct_regime = market_regime == required_regime
            self._log_criteria("Market Regime Filter (Adaptive)", is_correct_regime, f"Market is '{market_regime}' (ADX Percentile={adx_percentile:.2f}%), Required: '{required_regime}'")
            if not is_correct_regime:
                self._log_final_decision("HOLD", f"Incorrect market regime for operation."); return None

        # STAGE 2: PRIMARY TRIGGER
        primary_signal = self._safe_get(indicators, ['ema_cross', 'analysis', 'signal'])
        if primary_signal not in ["Buy", "Sell"]:
            self._log_final_decision("HOLD", "No primary EMA Cross trigger."); return None
        self._log_criteria("Primary Trigger (EMA Cross)", True, f"Signal: {primary_signal}")
        signal_direction = primary_signal.upper()
        
        # STAGE 3: DEFENSIVE SHIELDS
        exhaustion_cfg = cfg.get('exhaustion_shield', {})
        if exhaustion_cfg.get('enabled', True) and exhaustion_cfg.get('mode') == 'dynamic':
            is_exhausted = self._is_trend_exhausted_dynamic(
                direction=signal_direction,
                rsi_lookback=exhaustion_cfg.get('dynamic_rsi_lookback', 120),
                rsi_buy_percentile=exhaustion_cfg.get('dynamic_overbought_percentile', 85),
                rsi_sell_percentile=exhaustion_cfg.get('dynamic_oversold_percentile', 15)
            )
            if is_exhausted:
                self._log_final_decision("HOLD", "Vetoed by Adaptive Trend Exhaustion Shield."); return None
        self._log_criteria("Defensive Shields", True, "Signal passed all veto filters.")

        # STAGE 4: OFFENSIVE SQUAD
        score = 0; confirmations: List[str] = []; weights = cfg.get('weights', {})
        if cfg.get('master_trend_filter_enabled'):
            ma_val = self._safe_get(indicators, [cfg.get('master_trend_ma_indicator'), 'values', 'ma_value'])
            if self._is_valid_number(self.price_data['close'], ma_val):
                if (signal_direction == "BUY" and self.price_data['close'] > ma_val) or \
                   (signal_direction == "SELL" and self.price_data['close'] < ma_val):
                    score += weights.get('master_trend', 0); confirmations.append("Master Trend")
        if weights.get('hidden_divergence'):
            div_analysis = self._safe_get(indicators, ['divergence', 'analysis'], {})
            is_confirmed = (signal_direction == "BUY" and div_analysis.get('has_hidden_bullish_divergence')) or \
                           (signal_direction == "SELL" and div_analysis.get('has_hidden_bearish_divergence'))
            if is_confirmed:
                score += weights.get('hidden_divergence', 0); confirmations.append("Hidden Divergence")
        if cfg.get('macd_confirmation_enabled'):
            histo = self._safe_get(indicators, ['macd', 'values', 'histogram'], 0)
            if (signal_direction == "BUY" and histo > 0) or (signal_direction == "SELL" and histo < 0):
                score += weights.get('macd', 0); confirmations.append("MACD")
        stoch_cfg = cfg.get('stochastic_confirm', {})
        if stoch_cfg.get('enabled', True):
            stoch_signal = self._safe_get(indicators, ['stochastic', 'analysis', 'crossover_signal'], {})
            is_aligned = stoch_signal.get('direction', '').upper() == signal_direction
            is_strong_enough = not stoch_cfg.get('require_strong_cross', True) or stoch_signal.get('strength') == 'Strong'
            if is_aligned and is_strong_enough:
                score += weights.get('stochastic_cross', 0); confirmations.append("Stochastic Cross")
        if cfg.get('adx_confirmation_enabled'):
            adx_percentile = self._safe_get(indicators, ['adx', 'analysis', 'adx_percentile'], 0.0)
            if adx_percentile >= cfg.get('min_adx_percentile', 70.0):
                score += weights.get('adx_strength', 0); confirmations.append("ADX Strength (Adaptive)")
        if cfg.get('volume_confirmation_enabled'):
            if self._get_volume_confirmation(): score += weights.get('volume', 0); confirmations.append("Volume")
        if cfg.get('htf_confirmation_enabled'):
            if self._get_trend_confirmation(signal_direction): score += weights.get('htf_alignment', 0); confirmations.append("HTF")
        if cfg.get('candlestick_confirmation_enabled'):
            if self._get_candlestick_confirmation(signal_direction): score += weights.get('candlestick', 0); confirmations.append("Candlestick")
        
        min_score = cfg.get('min_confirmation_score', 12)
        if score < min_score:
            self._log_final_decision("HOLD", f"Confirmation score {score} is below required {min_score}."); return None
        self._log_criteria("Confirmation Score", True, f"Score: {score} >= Min: {min_score}. Confirmed by: {', '.join(confirmations)}")

        # --- STAGE 5: LOGISTICS (Perfected OHRE Integration) ---
        entry_price = self.price_data.get('close')
        long_ema_val = self._safe_get(indicators, ['ema_cross', 'values', 'long_ema'])
        atr_value = self._safe_get(indicators, ['atr', 'values', 'atr'])
        if not self._is_valid_number(entry_price, long_ema_val, atr_value):
            self._log_final_decision("HOLD", "Risk data missing for anchor calculation."); return None
            
        vol_cfg = cfg.get('volatility_regimes', {})
        atr_pct = self._safe_get(indicators, ['atr', 'values', 'atr_percent'], 2.0)
        is_low_vol = atr_pct < vol_cfg.get('low_atr_pct_threshold', 1.5)
        atr_sl_multiplier = vol_cfg.get('low_vol_sl_multiplier', 2.0) if is_low_vol else vol_cfg.get('high_vol_sl_multiplier', 3.0)
        
        sl_anchor_price = long_ema_val - (atr_value * atr_sl_multiplier) if signal_direction == "BUY" else long_ema_val + (atr_value * atr_sl_multiplier)
        
        risk_params = self._orchestrate_static_risk(
            direction=signal_direction,
            entry_price=entry_price,
            sl_anchor_price=sl_anchor_price
        )
        
        if not risk_params:
            self._log_final_decision("HOLD", "OHRE failed to generate a valid risk plan."); return None
        
        confirmations_dict = {
            "score": score, 
            "confirmations_passed": ", ".join(confirmations),
            "risk_engine": self.log_details["risk_trace"][-1].get("source", "OHRE"),
            "risk_reward": risk_params.get('risk_reward_ratio')
        }
        self._log_final_decision(signal_direction, f"Quantum Strategist assembled. Score: {score}. Risk plan by OHRE.")

        return { "direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations_dict }
