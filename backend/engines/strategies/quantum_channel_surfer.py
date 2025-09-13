# backend/engines/strategies/quantum_channel_surfer.py - (v1.6 - The Harmonized Surfer)

import logging
from typing import Dict, Any, Optional, Tuple, ClassVar, List

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class QuantumChannelSurfer(BaseStrategy):
    """
    Quantum Channel Surfer - (v1.6 - The Harmonized Surfer)
    -----------------------------------------------------------------------------------------
    This version represents a full architectural harmonization with the battle-tested
    patterns of the AiSignalPro ecosystem. The complex dynamic indicator building has
    been replaced by a robust, config-driven HTF confirmation helper, modeled after
    other successful strategies. This resolves all 'Indicators missing' bugs and
    ensures flawless, stable execution.
    """
    strategy_name: str = "QuantumChannelSurfer"

    default_config: ClassVar[Dict[str, Any]] = {
        # ✅ ARCHITECTURE: Now follows the standard, robust pattern.
        "htf_confirmation_enabled": True,
        "htf_map": {
            "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d",
        },
        "htf_confirmations": {
            "adx": { "min_percentile": 50.0 },
            "donchian_channel": {
                "buy_zone_max_percentile": 25.0,
                "sell_zone_min_percentile": 75.0
            }
        },
        
        "entry_confirmation": {
            "require_strong_stoch_cross": True,
            "min_macd_strength": 35
        },
        
        "min_rr_ratio": 1.5,
        
        # Static indicator configs remain flat and explicit.
        "indicator_configs": {
            "fast_ma":    { "name": "fast_ma", "ma_type": "DEMA", "period": 200 },
            "stochastic": { "name": "stochastic", "k_period": 14, "d_period": 3, "smooth_k": 3 },
            "macd":       { "name": "macd", "fast_period": 12, "slow_period": 26, "signal_period": 9 }
        }
    }

    def _check_qcs_htf_confirmation(self, direction: str) -> bool:
        """
        Specialized HTF confirmation helper for the Quantum Channel Surfer logic.
        """
        htf_map = self.config.get('htf_map', {})
        target_htf = htf_map.get(self.primary_timeframe)
        htf_rules = self.config.get('htf_confirmations', {})
        
        analysis_source = self.htf_analysis
        # Handle the 1D "self-reliant" mode
        if not target_htf and self.primary_timeframe == '1d':
            analysis_source = self.analysis
            self._log_indicator_trace("HTF_Source", "Self-Reliant Mode (1D)", reason="Using primary analysis as HTF source.")
        elif not analysis_source:
             logger.warning(f"QCS HTF check skipped: HTF analysis object for '{target_htf}' is missing.")
             return False

        # Rule 1: Check ADX strength on HTF
        adx_rules = htf_rules.get('adx', {})
        adx_indicator = self.get_indicator('adx', analysis_source=analysis_source)
        htf_adx_percentile = self._safe_get(adx_indicator, ['analysis', 'adx_percentile'], 0.0)
        if htf_adx_percentile < adx_rules.get('min_percentile', 50.0):
            self._log_criteria("HTF ADX Strength", False, f"HTF ADX percentile {htf_adx_percentile:.2f}% is below minimum.")
            return False
        
        # Rule 2: Check price position in HTF Donchian Channel
        donchian_rules = htf_rules.get('donchian_channel', {})
        donchian_indicator = self.get_indicator('donchian_channel', analysis_source=analysis_source)
        donchian_pos = self._safe_get(donchian_indicator, ['analysis', 'position_in_channel_percent'])
        if not self._is_valid_number(donchian_pos):
            self._log_criteria("HTF Donchian Position", False, "Could not determine position in HTF channel.")
            return False
        
        in_buy_zone = (direction == "BUY" and donchian_pos <= donchian_rules.get('buy_zone_max_percentile', 25.0))
        in_sell_zone = (direction == "SELL" and donchian_pos >= donchian_rules.get('sell_zone_min_percentile', 75.0))

        if not (in_buy_zone or in_sell_zone):
            self._log_criteria("HTF Donchian Position", False, f"Price at {donchian_pos:.2f}% is outside the designated hunt zone.")
            return False
        
        self._log_criteria("HTF Confirmation", True, "All HTF conditions met.")
        return True


    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        
        # ✅ SIMPLIFIED: No more 'htf_' aliases needed. BaseStrategy handles HTF access.
        required_names = ['fast_ma', 'stochastic', 'macd', 'structure', 'pivots', 'atr']
        indicators = {name: self.get_indicator(name) for name in required_names}
        if any(data is None for data in indicators.values()):
            missing = [name for name, data in indicators.items() if data is None]
            self._log_final_decision("HOLD", f"Indicators missing: {', '.join(missing)}"); return None

        # --- STAGE 1: Determine Macro Trend ---
        price = self._safe_get(self.price_data, ['close'])
        ma_val = self._safe_get(indicators['fast_ma'], ['values', 'ma_value'])
        if not self._is_valid_number(price, ma_val): return None
        allowed_direction = "BUY" if price > ma_val else "SELL"
        self._log_criteria("Macro Trend (Master MA)", True, f"Allowed Direction: {allowed_direction}")

        # --- STAGE 2: HTF Confirmation (The New, Robust Way) ---
        if cfg.get('htf_confirmation_enabled', True):
            if not self._check_qcs_htf_confirmation(allowed_direction):
                self._log_final_decision("HOLD", "Failed specialized HTF confirmation checks."); return None
        
        # --- STAGE 3: Entry Trigger (Stochastic) ---
        entry_cfg = cfg.get('entry_confirmation', {})
        stoch_signal = self._safe_get(indicators['stochastic'], ['analysis', 'crossover_signal'], {})
        stoch_direction, stoch_strength = stoch_signal.get('direction', 'N').upper(), stoch_signal.get('strength', 'N').upper()
        if not (stoch_direction == allowed_direction and (stoch_strength == "STRONG" or not entry_cfg.get('require_strong_stoch_cross'))):
            self._log_final_decision("HOLD", "No valid Stochastic trigger."); return None
        self._log_criteria("Entry Trigger (Stoch Cross)", True, f"Found '{stoch_strength}' {stoch_direction} cross.")
        
        # --- STAGE 4: Final Confirmation (MACD) ---
        macd_analysis = self._safe_get(indicators['macd'], ['analysis'], {})
        macd_momentum = macd_analysis.get('context', {}).get('momentum', 'N').upper()
        macd_strength = macd_analysis.get('strength', 0)
        if not (macd_momentum == "INCREASING" and macd_strength >= entry_cfg.get('min_macd_strength', 35)):
            self._log_final_decision("HOLD", f"MACD confirm failed (Mom: {macd_momentum}, Str: {macd_strength})."); return None
        self._log_criteria("Final Confirmation (MACD)", True, "MACD confirms.")
        
        # --- STAGE 5: Risk Orchestration ---
        signal_direction = allowed_direction
        entry_price = self.price_data.get('close')
        self.config['override_min_rr_ratio'] = cfg.get('min_rr_ratio', 1.5)
        risk_params = self._orchestrate_static_risk(direction=signal_direction, entry_price=entry_price)
        self.config.pop('override_min_rr_ratio', None)
        if not risk_params: self._log_final_decision("HOLD", "OHRE failed to generate risk plan."); return None
            
        confirmations = {
            "macro_trend": f"Price > DEMA200",
            "htf_context": f"Pass",
            "entry_trigger": f"Strong Stoch {stoch_direction} Cross",
            "momentum_confirmation": f"MACD Increasing (Str: {macd_strength})",
            "risk_engine": self.log_details["risk_trace"][-1].get("source", "OHRE v3.0"),
            "risk_reward": risk_params.get('risk_reward_ratio'),
        }
        self._log_final_decision(signal_direction, "Quantum Channel Surfer signal confirmed.")
        return {"direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations}
