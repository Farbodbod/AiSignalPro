# backend/engines/strategies/volume_catalyst.py (v6.0 - BlackBox Diagnostic)
import logging
from typing import Dict, Any, Optional, Tuple, List
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class VolumeCatalystPro(BaseStrategy):
    strategy_name: str = "VolumeCatalystPro"
    default_config = { "min_quality_score": 7, "weights": { "volume_catalyst_strength": 4, "momentum_thrust": 3, "volatility_release": 3, }, "cci_threshold": 100.0, "atr_sl_multiplier": 1.0, "min_rr_ratio": 2.0, "htf_confirmation_enabled": True, "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" }, "htf_confirmations": { "min_required_score": 2, "adx": {"weight": 1, "min_strength": 25}, "supertrend": {"weight": 1} } }

    def _calculate_breakout_quality_score(self, direction: str, whales_data: Dict, cci_data: Dict, bollinger_data: Dict) -> tuple[int, List[str]]:
        cfg, weights, score, confirmations = self.config, self.config.get('weights', {}), 0, []
        if whales_data['analysis'].get('is_whale_activity'):
            whale_pressure = whales_data['analysis'].get('pressure', '')
            if (direction == "BUY" and "Buying" in whale_pressure) or (direction == "SELL" and "Selling" in whale_pressure):
                score += weights.get('volume_catalyst_strength', 4); spike_score = whales_data['analysis'].get('spike_score', 0); confirmations.append(f"Volume Catalyst (Score: {spike_score:.2f})")
        cci_value = cci_data.get('values', {}).get('value', 0)
        if (direction == "BUY" and cci_value > cfg.get('cci_threshold', 100.0)) or (direction == "SELL" and cci_value < -cfg.get('cci_threshold', 100.0)):
            score += weights.get('momentum_thrust', 3); confirmations.append(f"Momentum Thrust (CCI: {cci_value:.2f})")
        if bollinger_data['analysis'].get('is_squeeze_release', False): score += weights.get('volatility_release', 3); confirmations.append("Volatility Release")
        return score, confirmations

    def _find_structural_breakout(self, structure_data: Dict) -> Optional[Tuple[str, float]]:
        try:
            if self.df is None or len(self.df) < 2: return None, None
            prev_close = self.df['close'].iloc[-2]
            current_price = self.price_data.get('close')
            
            # This is the area that was causing the crash.
            analysis_block = structure_data.get('analysis', {})
            if analysis_block is None: analysis_block = {}

            prox_analysis = analysis_block.get('proximity', {})
            if prox_analysis is None: prox_analysis = {}
            
            nearest_resistance = prox_analysis.get('nearest_resistance_details', {}).get('price')
            if nearest_resistance and prev_close <= nearest_resistance < current_price:
                return "BUY", nearest_resistance

            nearest_support = prox_analysis.get('nearest_support_details', {}).get('price')
            if nearest_support and prev_close >= nearest_support > current_price:
                return "SELL", nearest_support
            return None, None
        except Exception as e:
            # ✅ BLACKBOX: If any error occurs, log the exact input data and exit gracefully.
            logger.error(f"CRASH AVOIDED in _find_structural_breakout. Reason: {e}. Offending structure_data: {structure_data}", exc_info=True)
            return None, None

    def check_signal(self) -> Optional[Dict[str, Any]]:
        # This version includes a blackbox to catch the persistent error.
        logger.info(f"--- Executing VolumeCatalystPro v6.0 ---")
        cfg = self.config
        if not self.price_data:
            self._log_final_decision("HOLD", "No price data available.")
            return None
        
        required_names = ['structure', 'whales', 'cci', 'keltner_channel', 'bollinger', 'atr']
        indicators = {name: self.get_indicator(name) for name in required_names}
        missing_indicators = [name for name, data in indicators.items() if data is None]

        if missing_indicators:
            reason = f"Invalid/Missing indicators: {', '.join(missing_indicators)}"
            self._log_criteria("Data Availability", False, reason)
            self._log_final_decision("HOLD", reason)
            return None
        self._log_criteria("Data Availability", True, "All required indicators are present.")

        signal_direction, broken_level = self._find_structural_breakout(indicators['structure'])
        
        trigger_is_ok = signal_direction is not None
        self._log_criteria("Primary Trigger (Structural Breakout)", trigger_is_ok, "No structural breakout detected.")
        if not trigger_is_ok:
            self._log_final_decision("HOLD", "No valid entry trigger.")
            return None
        
        bqs, score_details = self._calculate_breakout_quality_score(signal_direction, indicators['whales'], indicators['cci'], indicators['bollinger'])
        min_score = cfg.get('min_quality_score', 7)
        score_is_ok = bqs >= min_score

        self._log_criteria("Breakout Quality Score Check", score_is_ok, f"Score of {bqs} is below minimum of {min_score}.")
        if not score_is_ok:
            self._log_final_decision("HOLD", "Breakout Quality Score is too low.")
            return None
        confirmations = {"breakout_quality_score": bqs, "score_details": ", ".join(score_details)}

        htf_ok = True
        if cfg['htf_confirmation_enabled']:
            htf_ok = self._get_trend_confirmation(signal_direction)
        self._log_criteria("HTF Filter", htf_ok, "Breakout is not aligned with the higher timeframe trend.")
        if not htf_ok:
            self._log_final_decision("HOLD", "HTF filter failed.")
            return None
        confirmations['htf_filter'] = "Passed (HTF Aligned)"
        
        entry_price = self.price_data.get('close')
        keltner_mid = indicators['keltner_channel'].get('values', {}).get('middle_band')
        atr_value = indicators['atr'].get('values', {}).get('atr')
        
        if not all([entry_price, keltner_mid, atr_value]):
            self._log_final_decision("HOLD", "Missing data for Stop Loss calculation (Keltner/ATR).")
            return None
        
        stop_loss = keltner_mid - (atr_value * cfg.get('atr_sl_multiplier', 1.0)) if signal_direction == "BUY" else keltner_mid + (atr_value * cfg.get('atr_sl_multiplier', 1.0))
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        
        min_rr = cfg.get('min_rr_ratio', 1.5)
        rr_is_ok = risk_params and risk_params.get("risk_reward_ratio", 0) >= min_rr
        self._log_criteria("Final R/R Check", rr_is_ok, f"Failed R/R check. (Calculated: {risk_params.get('risk_reward_ratio', 0)}, Required: {min_rr})")
        if not rr_is_ok:
            self._log_final_decision("HOLD", "Final R/R check failed.")
            return None
        confirmations['rr_check'] = f"Passed (R/R: {risk_params.get('risk_reward_ratio', 0):.2f})"
        
        self._log_final_decision(signal_direction, "All criteria met. Volume Catalyst signal confirmed.")
        return { "direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations }

