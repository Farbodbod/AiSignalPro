# engines/signal_adapter.py (نسخه 8.0 با برچسب استراتژی و زمان اعتبار)

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import uuid

class SignalAdapter:
    def __init__(self, analytics_output: Dict[str, Any], **kwargs):
        self.analytics = analytics_output or {}
        self.ai_confirmation = self.analytics.get("gemini_confirmation", {})
        self.details = self.analytics.get("details", {})

    def _calculate_valid_until(self, timeframe: str) -> str:
        """زمان اعتبار سیگنال را بر اساس تایم فریم محاسبه می‌کند."""
        now = datetime.utcnow()
        if timeframe == '5m':
            valid_until = now + timedelta(minutes=30)
        elif timeframe == '15m':
            valid_until = now + timedelta(hours=2)
        elif timeframe == '1h':
            valid_until = now + timedelta(hours=6)
        elif timeframe == '4h':
            valid_until = now + timedelta(hours=24)
        else:
            valid_until = now + timedelta(days=2)
        return valid_until.replace(microsecond=0).isoformat() + "Z"

    def generate_final_signal(self) -> Optional[Dict[str, Any]]:
        rule_based_signal = self.analytics.get("rule_based_signal", "HOLD")
        ai_signal = self.ai_confirmation.get("signal", "HOLD").upper()
        if ai_signal in ["N/A", "ERROR"]: ai_signal = "HOLD"
        
        is_contradictory = (rule_based_signal == "BUY" and ai_signal == "SELL") or (rule_based_signal == "SELL" and ai_signal == "BUY")
        final_signal = "HOLD" if is_contradictory or rule_based_signal == "HOLD" else rule_based_signal
        
        if final_signal == "HOLD": return None

        strategy_data, primary_tf_with_strategy = {}, None
        for tf in ['1h', '4h', '1d', '15m', '5m']:
            current_strategy = self.details.get(tf, {}).get("strategy", {})
            if current_strategy and current_strategy.get("targets"):
                strategy_data = current_strategy; primary_tf_with_strategy = tf; break
        
        if not strategy_data: return None

        symbol = self.details.get(primary_tf_with_strategy, {}).get("symbol", "N/A")
        if symbol == "N/A": return None

        final_payload = {
            "signal_id": str(uuid.uuid4()),
            "symbol": symbol,
            "timeframe": primary_tf_with_strategy,
            "signal_type": final_signal,
            "current_price": strategy_data.get("entry_price"),
            "entry_zone": strategy_data.get("entry_zone", []),
            "targets": strategy_data.get("targets", []),
            "stop_loss": strategy_data.get("stop_loss"),
            "risk_reward_ratio": strategy_data.get("risk_reward_ratio"),
            "strategy_name": strategy_data.get("strategy_name", "Pivot Reversion"), # <-- برچسب استراتژی
            "valid_until": self._calculate_valid_until(primary_tf_with_strategy), # <-- زمان اعتبار
            "ai_confidence_percent": self.ai_confirmation.get("confidence", 0),
            "system_confidence_percent": round(abs(self.analytics.get("buy_score", 0) - self.analytics.get("sell_score", 0)) * 10, 2),
            "explanation_fa": self.ai_confirmation.get("explanation_fa", "AI analysis not available."),
            "issued_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        }
        return final_payload
