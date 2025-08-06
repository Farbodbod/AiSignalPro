# engines/strategies/trend_rider.py (v2.0 - MTF Aware)

import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class TrendRiderStrategy(BaseStrategy):
    def __init__(self, analysis_summary: Dict[str, Any], config: Dict[str, Any] = None, htf_analysis: Optional[Dict[str, Any]] = None):
        super().__init__(analysis_summary, config, htf_analysis)
        self.strategy_name = "TrendRider"

    def _get_signal_config(self) -> Dict[str, Any]:
        return {"min_adx_strength": self.config.get("min_adx_strength", 25)}

    def check_signal(self) -> Optional[Dict[str, Any]]:
        supertrend_data = self.analysis.get('supertrend')
        adx_data = self.analysis.get('adx')
        entry_price = self.analysis.get('price_data', {}).get('close')

        if not all([supertrend_data, adx_data, entry_price]): return None

        htf_trend_aligned = False
        htf_supertrend_data = self.htf_analysis.get('supertrend') if self.htf_analysis else None
        
        signal_direction = None
        if supertrend_data['signal'] == "Bullish Trend Change":
            signal_direction = "BUY"
            if htf_supertrend_data and htf_supertrend_data.get('trend') == "Uptrend":
                htf_trend_aligned = True
        elif supertrend_data['signal'] == "Bearish Trend Change":
            signal_direction = "SELL"
            if htf_supertrend_data and htf_supertrend_data.get('trend') == "Downtrend":
                htf_trend_aligned = True
        
        if not signal_direction: return None
        if not htf_trend_aligned:
            logger.info(f"[{self.strategy_name}] Signal for {signal_direction} ignored. Not aligned with HTF trend.")
            return None
        
        cfg = self._get_signal_config()
        if adx_data['adx'] < cfg['min_adx_strength']: return None
        
        stop_loss = supertrend_data['value']
        risk_params = self._calculate_risk_management(entry_price, signal_direction, stop_loss)
        
        confirmations = {
            "supertrend_signal": supertrend_data['signal'],
            "adx_strength": round(adx_data['adx'], 2),
            "htf_confirmation": "Aligned"
        }
        return {
            "strategy_name": self.strategy_name, "direction": signal_direction,
            "entry_price": entry_price, **risk_params, "confirmations": confirmations
        }
