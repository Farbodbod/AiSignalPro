# engines/strategies/ichimoku_pro.py (v2.0 - MTF Aware)
import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class IchimokuProStrategy(BaseStrategy):
    def __init__(self, analysis_summary: Dict[str, Any], config: Dict[str, Any] = None, htf_analysis: Optional[Dict[str, Any]] = None):
        super().__init__(analysis_summary, config, htf_analysis)
        self.strategy_name = "IchimokuPro"
    
    # ... (بقیه متدهای این کلاس بدون تغییر هستند)
    def _get_signal_config(self) -> Dict[str, Any]: return {"min_score_to_signal": self.config.get("min_score_to_signal", 5)}
    def check_signal(self) -> Optional[Dict[str, Any]]: #... (کد کامل از قبل)
        ichimoku_data = self.analysis.get('ichimoku'); price_data = self.analysis.get('price_data');
        if not all([ichimoku_data, price_data]): return None
        cfg = self._get_signal_config(); buy_score, sell_score = 0, 0; confirmations = [];
        price_pos = ichimoku_data.get('price_position'); tk_cross = ichimoku_data.get('signal', 'Neutral'); chikou_confirm = ichimoku_data.get('chikou_confirmation'); price = price_data.get('close'); kijun = ichimoku_data.get('kijun_sen'); senkou_a = ichimoku_data.get('senkou_span_a'); senkou_b = ichimoku_data.get('senkou_span_b')
        if price_pos == "Above Kumo": buy_score += 3; confirmations.append("Above Kumo")
        elif price_pos == "Below Kumo": sell_score += 3; confirmations.append("Below Kumo")
        if "Bullish" in tk_cross: buy_score += 2; confirmations.append(tk_cross)
        elif "Bearish" in tk_cross: sell_score += 2; confirmations.append(tk_cross)
        if chikou_confirm == "Bullish Confirmation": buy_score += 1; confirmations.append(chikou_confirm)
        elif chikou_confirm == "Bearish Confirmation": sell_score += 1; confirmations.append(chikou_confirm)
        if price > kijun: buy_score += 1; confirmations.append("Price above Kijun")
        elif price < kijun: sell_score += 1; confirmations.append("Price below Kijun")
        if senkou_a > senkou_b: buy_score += 1; confirmations.append("Future Kumo is Bullish")
        elif senkou_a < senkou_b: sell_score += 1; confirmations.append("Future Kumo is Bearish")
        signal_direction = None
        if buy_score >= cfg['min_score_to_signal']: signal_direction = "BUY"
        elif sell_score >= cfg['min_score_to_signal']: signal_direction = "SELL"
        if not signal_direction: return None
        atr_val = self.analysis.get('atr', {}).get('value', price * 0.015)
        stop_loss = kijun - atr_val if signal_direction == "BUY" else kijun + atr_val
        risk_params = self._calculate_risk_management(price, signal_direction, stop_loss)
        return {"strategy_name": self.strategy_name, "direction": signal_direction, "entry_price": price, **risk_params, "confirmations": confirmations}
