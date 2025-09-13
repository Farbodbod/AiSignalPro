# backend/engines/strategies/quantum_channel_surfer.py - (v1.5 - The Sentinel Protocol)

import logging
from typing import Dict, Any, Optional, Tuple, ClassVar, List

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class QuantumChannelSurfer(BaseStrategy):
    """
    Quantum Channel Surfer - (v1.5 - The Sentinel Protocol)
    -----------------------------------------------------------------------------------------
    This version applies a critical hotfix to the dynamic indicator builder. It ensures
    that dynamically generated indicator configurations (for HTF analysis) are created
    with the nested 'params' structure required by the BaseStrategy's get_indicator
    method. This fixes the 'Indicators missing' bug and brings the strategy into
    full compliance with the system's internal lookup protocol, making it truly
    production-ready.
    """
    strategy_name: str = "QuantumChannelSurfer"

    default_config: ClassVar[Dict[str, Any]] = {
        "htf_donchian_map": {
            "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d",
        },
        "macro_trend_filter": { "min_htf_adx_percentile": 50.0 },
        "entry_zone": { "buy_zone_max_percentile": 25.0, "sell_zone_min_percentile": 75.0 },
        "entry_confirmation": { "require_strong_stoch_cross": True, "min_macd_strength": 35 },
        "min_rr_ratio": 1.5,
        
        # The static configs remain flat and explicit as per our architectural decision.
        "indicator_configs": {
            "fast_ma":    { "name": "fast_ma", "ma_type": "DEMA", "period": 200 },
            "stochastic": { "name": "stochastic", "k_period": 14, "d_period": 3, "smooth_k": 3 },
            "macd":       { "name": "macd", "fast_period": 12, "slow_period": 26, "signal_period": 9 }
        }
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._build_dynamic_indicator_configs()

    def _build_dynamic_indicator_configs(self):
        """
        ✅ CRITICAL HOTFIX: Builds dynamic configs with the nested 'params' structure
        required by the BaseStrategy's get_indicator helper function.
        """
        htf_donchian_map = self.config.get("htf_donchian_map", {})
        target_tf = htf_donchian_map.get(self.primary_timeframe)
        
        if not target_tf and self.primary_timeframe == '1d':
            target_tf = '1d' 
            logger.info(f"QCS on {self.primary_timeframe}: No higher map found. Activating 'Self-Reliant' mode.")
        
        if target_tf:
            # Build with the required nested 'params' structure
            self.indicator_configs['htf_donchian'] = { 
                "name": "donchian_channel", 
                "params": { 
                    "period": 55, 
                    "source_timeframe": target_tf 
                }
            }
            self.indicator_configs['htf_adx'] = { 
                "name": "adx", 
                "params": { 
                    "period": 14, 
                    "timeframe": target_tf 
                }
            }
        else:
            logger.warning(f"QCS on {self.primary_timeframe}: No HTF map defined. Strategy will be inactive.")
            self.indicator_configs.pop('htf_donchian', None)
            self.indicator_configs.pop('htf_adx', None)
    
    # The check_signal function remains IDENTICAL. No changes are needed here.
    def check_signal(self) -> Optional[Dict[str, Any]]:
        # ... (کد این تابع بدون هیچ تغییری باقی می‌ماند) ...
        cfg = self.config
        required_names = ['fast_ma', 'htf_adx', 'htf_donchian', 'stochastic', 'macd', 'structure', 'pivots', 'atr']
        indicators = {name: self.get_indicator(name) for name in required_names}
        if any(data is None for data in indicators.values()):
            missing = [name for name, data in indicators.items() if data is None]
            self._log_final_decision("HOLD", f"Indicators missing: {', '.join(missing)}"); return None
        price = self._safe_get(self.price_data, ['close'])
        ma_val = self._safe_get(indicators['fast_ma'], ['values', 'ma_value'])
        if not self._is_valid_number(price, ma_val):
            self._log_final_decision("HOLD", "Invalid price or MA value."); return None
        allowed_direction = "BUY" if price > ma_val else "SELL"
        self._log_criteria("Macro Trend (Master MA)", True, f"Allowed Direction: {allowed_direction}")
        macro_cfg = cfg.get('macro_trend_filter', {})
        htf_adx_percentile = self._safe_get(indicators['htf_adx'], ['analysis', 'adx_percentile'], 0.0)
        if htf_adx_percentile < macro_cfg.get('min_htf_adx_percentile', 50.0):
            self._log_final_decision("HOLD", f"HTF trend weak (ADX %: {htf_adx_percentile:.2f})"); return None
        self._log_criteria("Macro Strength (HTF ADX)", True, f"HTF trend strong.")
        zone_cfg = cfg.get('entry_zone', {})
        donchian_pos = self._safe_get(indicators['htf_donchian'], ['analysis', 'position_in_channel_percent'])
        if not self._is_valid_number(donchian_pos):
            self._log_final_decision("HOLD", "Could not get position in HTF Donchian."); return None
        in_buy_zone = (allowed_direction == "BUY" and donchian_pos <= zone_cfg.get('buy_zone_max_percentile', 25.0))
        in_sell_zone = (allowed_direction == "SELL" and donchian_pos >= zone_cfg.get('sell_zone_min_percentile', 75.0))
        if not (in_buy_zone or in_sell_zone):
            self._log_final_decision("HOLD", f"Price not in hunt zone (Pos: {donchian_pos:.2f}%)"); return None
        self._log_criteria("Entry Zone (HTF Donchian)", True, f"Price in {allowed_direction} zone.")
        entry_cfg = cfg.get('entry_confirmation', {})
        stoch_signal = self._safe_get(indicators['stochastic'], ['analysis', 'crossover_signal'], {})
        stoch_direction, stoch_strength = stoch_signal.get('direction', 'N').upper(), stoch_signal.get('strength', 'N').upper()
        if not (stoch_direction == allowed_direction and (stoch_strength == "STRONG" or not entry_cfg.get('require_strong_stoch_cross'))):
            self._log_final_decision("HOLD", "No valid Stochastic trigger."); return None
        self._log_criteria("Entry Trigger (Stoch Cross)", True, f"Found '{stoch_strength}' {stoch_direction} cross.")
        macd_analysis = self._safe_get(indicators['macd'], ['analysis'], {})
        macd_momentum = macd_analysis.get('context', {}).get('momentum', 'N').upper()
        macd_strength = macd_analysis.get('strength', 0)
        if not (macd_momentum == "INCREASING" and macd_strength >= entry_cfg.get('min_macd_strength', 35)):
            self._log_final_decision("HOLD", f"MACD confirm failed (Mom: {macd_momentum}, Str: {macd_strength})."); return None
        self._log_criteria("Final Confirmation (MACD)", True, "MACD confirms.")
        signal_direction = allowed_direction
        entry_price = self.price_data.get('close')
        self.config['override_min_rr_ratio'] = cfg.get('min_rr_ratio', 1.5)
        risk_params = self._orchestrate_static_risk(direction=signal_direction, entry_price=entry_price)
        self.config.pop('override_min_rr_ratio', None)
        if not risk_params:
            self._log_final_decision("HOLD", "OHRE failed to generate risk plan."); return None
        confirmations = {
            "macro_trend": f"Price > DEMA200, HTF ADX% > {macro_cfg.get('min_htf_adx_percentile', 50.0)}",
            "entry_trigger": f"Strong Stoch {stoch_direction} Cross in Donchian Zone ({donchian_pos:.1f}%)",
            "momentum_confirmation": f"MACD Increasing (Str: {macd_strength})",
            "risk_engine": self.log_details["risk_trace"][-1].get("source", "OHRE v3.0"),
            "risk_reward": risk_params.get('risk_reward_ratio'),
        }
        self._log_final_decision(signal_direction, "Quantum Channel Surfer signal confirmed.")
        return {"direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations}
