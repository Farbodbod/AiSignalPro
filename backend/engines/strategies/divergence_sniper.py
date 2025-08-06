# engines/strategies/divergence_sniper.py (v2.0 - MTF Aware)
import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class DivergenceSniperStrategy(BaseStrategy):
    def __init__(self, analysis_summary: Dict[str, Any], config: Dict[str, Any] = None, htf_analysis: Optional[Dict[str, Any]] = None):
        super().__init__(analysis_summary, config, htf_analysis)
        self.strategy_name = "DivergenceSniper"

    # ... (بقیه متدهای این کلاس بدون تغییر هستند)
    def _get_signal_config(self) -> Dict[str, Any]: return {"bullish_reversal_patterns": self.config.get("bullish_reversal_patterns", ['HAMMER', 'MORNINGSTAR', 'BULLISHENGULFING']), "bearish_reversal_patterns": self.config.get("bearish_reversal_patterns", ['SHOOTINGSTAR', 'EVENINGSTAR', 'BEARISHENGULFING'])}
    def _has_reversal_pattern(self, direction: str) -> bool: #... (کد کامل از قبل)
        found_patterns = self.analysis.get('patterns', {}).get('patterns', []);
        if not found_patterns: return False;
        target_patterns = self._get_signal_config()['bullish_reversal_patterns'] if direction == "BUY" else self._get_signal_config()['bearish_reversal_patterns'];
        return any(p.upper() in target_patterns for p in found_patterns)
    def check_signal(self) -> Optional[Dict[str, Any]]: #... (کد کامل از قبل)
        divergence_data = self.analysis.get('divergence'); structure_data = self.analysis.get('structure'); price_data = self.analysis.get('price_data')
        if not all([divergence_data, structure_data, price_data]): return None
        signal_direction = None
        if divergence_data['type'] == "Bullish" and divergence_data['strength'] == "Strong": signal_direction = "BUY"
        elif divergence_data['type'] == "Bearish" and divergence_data['strength'] == "Strong": signal_direction = "SELL"
        if not signal_direction or not self._has_reversal_pattern(signal_direction): return None
        entry_price = price_data['close']; key_levels = structure_data.get('key_levels', {}); stop_loss = None
        if signal_direction == "BUY" and key_levels.get('supports'): stop_loss = key_levels.get('supports')[0] * 0.998
        elif signal_direction == "SELL" and key_levels.get('resistances'): stop_loss = key_levels.get('resistances')[0] * 1.002
        if stop_loss is None: return None
        risk_params = self._calculate_risk_management(entry_price, signal_direction, stop_loss)
        return {"strategy_name": self.strategy_name, "direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": {"divergence_type": f"{divergence_data['strength']} {divergence_data['type']}", "reversal_patterns": self.analysis.get('patterns', {}).get('patterns', [])}}
