# engines/strategies/pivot_reversal.py (v2.0 - MTF Aware)
import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class PivotReversalStrategy(BaseStrategy):
    def __init__(self, analysis_summary: Dict[str, Any], config: Dict[str, Any] = None, htf_analysis: Optional[Dict[str, Any]] = None):
        super().__init__(analysis_summary, config, htf_analysis)
        self.strategy_name = "PivotSniper"
    
    # ... (بقیه متدهای این کلاس بدون تغییر هستند)
    def _get_signal_config(self) -> Dict[str, Any]: return {"proximity_percent": self.config.get("proximity_percent", 0.002), "stoch_oversold": self.config.get("stoch_oversold", 25), "stoch_overbought": self.config.get("stoch_overbought", 75), "pivot_levels_to_check": self.config.get("pivot_levels_to_check", ['R2', 'R1', 'S1', 'S2'])}
    def check_signal(self) -> Optional[Dict[str, Any]]: #... (کد کامل از قبل)
        pivots_data = self.analysis.get('pivots'); stoch_data = self.analysis.get('stochastic'); price_data = self.analysis.get('price_data')
        if not all([pivots_data, stoch_data, price_data]): return None
        cfg = self._get_signal_config(); current_price = price_data['close']; pivot_levels = pivots_data.get('levels', {}); signal_direction = None; trigger_level_name = None
        for level_name in cfg['pivot_levels_to_check']:
            level_price = pivot_levels.get(level_name);
            if not level_price: continue
            if abs(current_price - level_price) / current_price < cfg['proximity_percent']:
                if level_name.startswith('S') and stoch_data['position'] == "Oversold" and stoch_data['percent_k'] < cfg['stoch_oversold']: signal_direction = "BUY"; trigger_level_name = level_name; break
                elif level_name.startswith('R') and stoch_data['position'] == "Overbought" and stoch_data['percent_k'] > cfg['stoch_overbought']: signal_direction = "SELL"; trigger_level_name = level_name; break
        if not signal_direction: return None
        atr_val = self.analysis.get('atr', {}).get('value', current_price * 0.01)
        stop_loss = level_price - atr_val if signal_direction == "BUY" else level_price + atr_val
        risk_params = self._calculate_risk_management(current_price, signal_direction, stop_loss)
        risk_params['targets'][0] = pivot_levels.get('P')
        return {"strategy_name": self.strategy_name, "direction": signal_direction, "entry_price": current_price, **risk_params, "confirmations": {"trigger_pivot_level": trigger_level_name, "stochastic_k": stoch_data['percent_k']}}
