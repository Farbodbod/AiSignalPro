# engines/signal_adapter.py (نسخه نهایی 2.3 - رفع خطا و بهبود امتیازدهی)

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import hashlib, logging

logger = logging.getLogger(__name__)

class SignalAdapter:
    # --- ✨ اصلاح کلیدی: تغییر نام پارامتر برای هماهنگی با views.py ---
    def __init__(self, analytics_output: Dict[str, Any]):
        self.output = analytics_output or {}
        self.ai_confirmation = self.output.get("gemini_confirmation", {})

    def _calculate_valid_until(self, timeframe: str) -> str:
        now = datetime.utcnow()
        try:
            if 'm' in timeframe: valid_until = now + timedelta(minutes=int(timeframe.replace('m', '')) * 6)
            elif 'h' in timeframe: valid_until = now + timedelta(hours=int(timeframe.replace('h', '')) * 4)
            else: valid_until = now + timedelta(hours=4)
            return valid_until.replace(microsecond=0).isoformat() + "Z"
        except Exception: return (now + timedelta(hours=4)).replace(microsecond=0).isoformat() + "Z"

    def generate_final_signal(self) -> Optional[Dict[str, Any]]:
        rule_based_signal = self.output.get("final_signal", "HOLD")
        ai_signal = str(self.ai_confirmation.get("signal", "HOLD")).upper()
        is_contradictory = (rule_based_signal == "BUY" and ai_signal == "SELL") or \
                          (rule_based_signal == "SELL" and ai_signal == "BUY")

        if rule_based_signal == "HOLD" or is_contradictory:
            if is_contradictory:
                logger.info(f"Signal for {self.output.get('symbol')} VETOED by AI.")
            return None
        
        strategy = self.output.get("winning_strategy")
        if not strategy: return None
        
        symbol, timeframe, entry_price = self.output.get("symbol"), strategy.get("timeframe"), strategy.get("entry_price")
        if not all([symbol, timeframe, entry_price]): return None
            
        signal_id = hashlib.md5(f"{symbol}_{timeframe}_{rule_based_signal}_{entry_price}".encode()).hexdigest()
        
        # --- ✨ اصلاح کلیدی: بهبود فرمول محاسبه امتیاز سیستم ---
        # سقف امتیاز را روی ۲۵ در نظر می‌گیریم تا مقادیر پویاتری داشته باشیم
        confidence = min(round((strategy.get('weighted_score', 0) / 25.0) * 100, 1), 100)
        
        return {
            "signal_id": signal_id, "symbol": symbol, "timeframe": timeframe,
            "signal_type": rule_based_signal, "current_price": entry_price,
            "entry_zone": strategy.get("entry_zone", []), 
            "targets": strategy.get("targets", []),
            "stop_loss": strategy.get("stop_loss"), 
            "risk_reward_ratio": strategy.get("risk_reward_ratio"),
            "strategy_name": strategy.get("strategy_name", "Unknown"),
            "valid_until": self._calculate_valid_until(timeframe),
            "system_confidence_percent": confidence,
            "ai_confidence_percent": self.ai_confirmation.get("confidence", 0),
            "explanation_fa": self.ai_confirmation.get("explanation_fa", "N/A"),
            "issued_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        }
