# engines/signal_adapter.py (نسخه نهایی و ضد خطا)
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import uuid, hashlib, logging

logger = logging.getLogger(__name__)

class SignalAdapter:
    def __init__(self, analytics_output: Dict[str, Any], **kwargs):
        self.analytics = analytics_output or {}; self.ai_confirmation = self.analytics.get("gemini_confirmation") or {}; self.details = self.analytics.get("details") or {}
    def _normalize_timeframe(self, timeframe: str) -> str:
        if not isinstance(timeframe, str): return "unknown"
        return timeframe.lower().replace("minute", "m").replace("min", "m").replace("hour", "h").replace("hr", "h").replace(" ", "")
    def _calculate_valid_until(self, timeframe: str) -> str:
        now = datetime.utcnow()
        try:
            tf = self._normalize_timeframe(timeframe)
            if 'm' in tf: valid_until = now + timedelta(minutes=int(tf.replace('m', '')) * 6)
            elif 'h' in tf: valid_until = now + timedelta(hours=int(tf.replace('h', '')) * 4)
            elif 'd' in tf: valid_until = now + timedelta(days=int(tf.replace('d', '')) * 2)
            else: valid_until = now + timedelta(hours=4)
            return valid_until.replace(microsecond=0).isoformat() + "Z"
        except Exception: return (now + timedelta(hours=4)).replace(microsecond=0).isoformat() + "Z"
    def generate_final_signal(self) -> Optional[Dict[str, Any]]:
        rule_based_signal = self.analytics.get("rule_based_signal", "HOLD")
        ai_signal = str(self.ai_confirmation.get("signal", "HOLD")).upper()
        if ai_signal in {"N/A", "ERROR", ""}: ai_signal = "HOLD"
        is_contradictory = (rule_based_signal == "BUY" and ai_signal == "SELL") or (rule_based_signal == "SELL" and ai_signal == "BUY")
        final_signal = "HOLD" if is_contradictory or rule_based_signal == "HOLD" else rule_based_signal
        if final_signal == "HOLD": return None
        strategy_data, primary_tf_with_strategy = {}, None
        for tf in ['4h', '1h', '15m', '5m']:
            current_analysis = self.details.get(tf)
            if not isinstance(current_analysis, dict): continue
            current_strategy = current_analysis.get("strategy", {})
            if current_strategy and current_strategy.get("targets"):
                strategy_data = current_strategy; primary_tf_with_strategy = tf; break
        if not strategy_data: return None
        symbol = self.details.get(primary_tf_with_strategy, {}).get("symbol", "N/A")
        if symbol == "N/A": return None
        required_keys = ["entry_price", "stop_loss", "targets", "strategy_name"]
        if not all(key in strategy_data for key in required_keys):
            logger.warning(f"Strategy data for {symbol}@{primary_tf_with_strategy} is incomplete. Signal rejected."); return None
        signal_str = f"{symbol}_{primary_tf_with_strategy}_{final_signal}_{strategy_data.get('entry_price')}"
        signal_id = hashlib.md5(signal_str.encode()).hexdigest()
        confidence_score = round(abs(self.analytics.get("buy_score", 0) - self.analytics.get("sell_score", 0)) * 10, 2)
        return {
            "signal_id": signal_id, "symbol": symbol, "timeframe": primary_tf_with_strategy,
            "signal_type": final_signal, "current_price": strategy_data.get("entry_price"),
            "entry_zone": strategy_data.get("entry_zone", []), "targets": strategy_data.get("targets", []),
            "stop_loss": strategy_data.get("stop_loss"), "risk_reward_ratio": strategy_data.get("risk_reward_ratio"),
            "strategy_name": strategy_data.get("strategy_name", "Unknown"), "strategy_meta": strategy_data.get("meta", {}),
            "valid_until": self._calculate_valid_until(primary_tf_with_strategy),
            "ai_confidence_percent": self.ai_confirmation.get("confidence", 0),
            "system_confidence_percent": max(confidence_score, 1.0),
            "explanation_fa": self.ai_confirmation.get("explanation_fa", "AI analysis not available."),
            "issued_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        }
