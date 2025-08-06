# engines/strategies/volume_catalyst.py (v2.0 - MTF Aware)
import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class VolumeCatalystStrategy(BaseStrategy):
    def __init__(self, analysis_summary: Dict[str, Any], config: Dict[str, Any] = None, htf_analysis: Optional[Dict[str, Any]] = None):
        super().__init__(analysis_summary, config, htf_analysis)
        self.strategy_name = "VolumeCatalyst"

    # ... (بقیه متدهای این کلاس بدون تغییر هستند)
    def check_signal(self) -> Optional[Dict[str, Any]]: #... (کد کامل از قبل)
        structure_data = self.analysis.get('structure'); whales_data = self.analysis.get('whales'); price_data = self.analysis.get('price_data');
        if not all([structure_data, whales_data, price_data]): return None
        key_levels = structure_data.get('key_levels', {}); supports = key_levels.get('supports', []); resistances = key_levels.get('resistances', []); current_price = price_data['close']; prev_price = self.analysis.get('price_data_prev', {}).get('close');
        if prev_price is None: return None
        signal_direction = None; broken_level = None
        if resistances and current_price > resistances[0] and prev_price < resistances[0]:
            if whales_data['status'] == 'Whale Activity Detected' and whales_data['pressure'] == 'Buying Pressure': signal_direction = "BUY"; broken_level = resistances[0]
        if not signal_direction and supports and current_price < supports[0] and prev_price > supports[0]:
            if whales_data['status'] == 'Whale Activity Detected' and whales_data['pressure'] == 'Selling Pressure': signal_direction = "SELL"; broken_level = supports[0]
        if not signal_direction: return None
        atr_val = self.analysis.get('atr', {}).get('value', current_price * 0.015)
        stop_loss = broken_level - atr_val if signal_direction == "BUY" else broken_level + atr_val
        risk_params = self._calculate_risk_management(current_price, signal_direction, stop_loss)
        return {"strategy_name": self.strategy_name, "direction": signal_direction, "entry_price": current_price, **risk_params, "confirmations": {"broken_level": broken_level, "volume_spike_factor": whales_data['spike_factor']}}
