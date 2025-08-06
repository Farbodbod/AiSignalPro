# engines/strategies/mean_reversion.py (v2.0 - MTF Aware)
import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class MeanReversionStrategy(BaseStrategy):
    # --- ✨ تغییر کلیدی: افزودن htf_analysis به امضای تابع ---
    def __init__(self, analysis_summary: Dict[str, Any], config: Dict[str, Any] = None, htf_analysis: Optional[Dict[str, Any]] = None):
        # --- ✨ پاس دادن پارامتر جدید به کلاس والد ---
        super().__init__(analysis_summary, config, htf_analysis)
        self.strategy_name = "MeanReversionPro"

    def _get_signal_config(self) -> Dict[str, Any]:
        return {"rsi_oversold": self.config.get("rsi_oversold", 30), "rsi_overbought": self.config.get("rsi_overbought", 70), "bb_buy_threshold": self.config.get("bb_buy_threshold", 0), "bb_sell_threshold": self.config.get("bb_sell_threshold", 1)}

    def check_signal(self) -> Optional[Dict[str, Any]]:
        # ... (منطق اصلی این تابع بدون تغییر است)
        bollinger_data = self.analysis.get('bollinger'); rsi_data = self.analysis.get('rsi'); price_data = self.analysis.get('price_data')
        if not all([bollinger_data, rsi_data, price_data]): return None
        cfg = self._get_signal_config(); entry_price = price_data['close']; signal_direction = None
        if bollinger_data['percent_b'] < cfg['bb_buy_threshold'] and rsi_data['value'] < cfg['rsi_oversold']: signal_direction = "BUY"
        elif bollinger_data['percent_b'] > cfg['bb_sell_threshold'] and rsi_data['value'] > cfg['rsi_overbought']: signal_direction = "SELL"
        if not signal_direction: return None
        risk_params = self._calculate_risk_management(entry_price, signal_direction, 0) # Note: SL needs context
        risk_params['targets'][0] = bollinger_data['middle_band']
        return {"strategy_name": self.strategy_name, "direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": {"bollinger_percent_b": bollinger_data['percent_b'],"rsi_value": rsi_data['value']}}
