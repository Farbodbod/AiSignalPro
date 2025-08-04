# engines/signal_adapter.py (نسخه نهایی 2.2 - کاملاً هماهنگ)
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import hashlib, logging

logger = logging.getLogger(__name__)

class SignalAdapter:
    def __init__(self, orchestrator_output: Dict[str, Any]):
        self.output = orchestrator_output or {}
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
        # --- ✨ اصلاح کلیدی: خواندن کلید صحیح از خروجی جدید ---
        rule_based_signal = self.output.get("final_signal", "HOLD")
        ai_signal = str(self.ai_confirmation.get("signal", "HOLD")).upper()

        # بررسی تناقض بین سیگنال سیستم و سیگنال AI
        is_contradictory = (rule_based_signal == "BUY" and ai_signal == "SELL") or \
                          (rule_based_signal == "SELL" and ai_signal == "BUY")

        # اگر سیگنال پایه HOLD است یا تناقض وجود دارد، سیگنال را لغو کن
        if rule_based_signal == "HOLD" or is_contradictory:
            if is_contradictory:
                logger.info(f"Signal for {self.output.get('symbol')} VETOED by AI. System: {rule_based_signal}, AI: {ai_signal}")
            return None
        
        strategy = self.output.get("winning_strategy")
        if not strategy: return None
        
        symbol = self.output.get("symbol", "N/A")
        timeframe = strategy.get("timeframe", "N/A")
        entry_price = strategy.get("entry_price")
        
        if any(x == "N/A" for x in [symbol, timeframe, entry_price]): return None
            
        signal_id = hashlib.md5(f"{symbol}_{timeframe}_{rule_based_signal}_{entry_price}".encode()).hexdigest()
        confidence = min(round((strategy.get('weighted_score', 0) / 15.0) * 100, 1), 100)
        
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
