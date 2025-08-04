from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import uuid
import hashlib
import logging

logger = logging.getLogger(__name__)

class SignalAdapter:
    def __init__(self, analytics_output: Dict[str, Any], **kwargs):
        self.analytics = analytics_output or {}
        self.ai_confirmation = self.analytics.get("gemini_confirmation", {})
        self.details = self.analytics.get("details", {})

    def _normalize_timeframe(self, timeframe: str) -> str:
        """استانداردسازی نام تایم‌فریم (مثلاً '15min' → '15m')"""
        tf = timeframe.lower().replace("minute", "m").replace("min", "m").replace("hour", "h").replace("hr", "h").replace(" ", "")
        return tf

    def _calculate_valid_until(self, timeframe: str) -> str:
        """محاسبه زمان اعتبار سیگنال بر اساس تایم‌فریم"""
        now = datetime.utcnow()
        try:
            tf = self._normalize_timeframe(timeframe)
            if 'm' in tf:
                minutes = int(tf.replace('m', ''))
                valid_until = now + timedelta(minutes=minutes * 6)
            elif 'h' in tf:
                hours = int(tf.replace('h', ''))
                valid_until = now + timedelta(hours=hours * 4)
            elif 'd' in tf:
                days = int(tf.replace('d', ''))
                valid_until = now + timedelta(days=days * 2)
            else:
                valid_until = now + timedelta(hours=4)
            return valid_until.replace(microsecond=0).isoformat() + "Z"
        except Exception:
            return (now + timedelta(hours=4)).replace(microsecond=0).isoformat() + "Z"

    def generate_final_signal(self) -> Optional[Dict[str, Any]]:
        rule_based_signal = self.analytics.get("rule_based_signal", "HOLD")
        ai_signal_raw = self.ai_confirmation.get("signal", "HOLD")
        ai_signal = str(ai_signal_raw).upper()
        if ai_signal in {"N/A", "ERROR", ""}:
            ai_signal = "HOLD"

        is_contradictory = (
            (rule_based_signal == "BUY" and ai_signal == "SELL") or
            (rule_based_signal == "SELL" and ai_signal == "BUY")
        )
        final_signal = "HOLD" if is_contradictory or rule_based_signal == "HOLD" else rule_based_signal
        if final_signal == "HOLD":
            return None

        strategy_data, primary_tf_with_strategy = {}, None
        for tf in ['4h', '1h', '15m', '5m']:
            current_strategy = self.details.get(tf, {}).get("strategy", {})
            if current_strategy and current_strategy.get("targets"):
                strategy_data = current_strategy
                primary_tf_with_strategy = tf
                break

        if not strategy_data:
            return None

        symbol = self.details.get(primary_tf_with_strategy, {}).get("symbol", "N/A")
        if symbol == "N/A":
            return None

        # بررسی کامل بودن فیلدهای حیاتی
        if not all([
            strategy_data.get("entry_price"),
            strategy_data.get("stop_loss"),
            strategy_data.get("targets")
        ]):
            return None

        # ساخت signal_id پایدار (در صورت تمایل می‌توان uuid استفاده کرد)
        signal_str = f"{symbol}_{primary_tf_with_strategy}_{final_signal}_{strategy_data.get('entry_price')}"
        signal_id = hashlib.md5(signal_str.encode()).hexdigest()

        final_payload = {
            "signal_id": signal_id,
            "symbol": symbol,
            "timeframe": primary_tf_with_strategy,
            "signal_type": final_signal,
            "current_price": strategy_data.get("entry_price"),
            "entry_zone": strategy_data.get("entry_zone", []),
            "targets": strategy_data.get("targets", []),
            "stop_loss": strategy_data.get("stop_loss"),
            "risk_reward_ratio": strategy_data.get("risk_reward_ratio"),
            "strategy_name": strategy_data.get("strategy_name", "Unknown"),
            "strategy_meta": strategy_data.get("meta", {}),  # فیلد جدید اختیاری
            "valid_until": self._calculate_valid_until(primary_tf_with_strategy),
            "ai_confidence_percent": self.ai_confirmation.get("confidence", 0),
            "system_confidence_percent": round(abs(self.analytics.get("buy_score", 0) - self.analytics.get("sell_score", 0)) * 10, 2),
            "explanation_fa": self.ai_confirmation.get("explanation_fa", "AI analysis not available."),
            "issued_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        }
        return final_payload
