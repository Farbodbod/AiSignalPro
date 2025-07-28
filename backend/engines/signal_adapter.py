# engines/signal_adapter.py (نسخه نهایی با منطق هوشمند استخراج استراتژی)

from typing import Dict, Any, Optional
from datetime import datetime
import uuid

class SignalAdapter:
    def __init__(self, analytics_output: Dict[str, Any], **kwargs):
        self.analytics = analytics_output or {}
        self.ai_confirmation = self.analytics.get("gemini_confirmation", {})
        self.details = self.analytics.get("details", {})

    def _get_primary_data(self, key: str, default: Any = None):
        """از اولین تایم فریم معتبر، یک مقدار خاص را استخراج می‌کند."""
        if not self.details: return default
        
        for tf in ['1h', '4h', '1d', '15m', '5m']:
            if tf in self.details and isinstance(self.details.get(tf), dict):
                if key in self.details[tf] and self.details[tf].get(key) is not None:
                    return self.details[tf][key]
                for sub_dict in self.details[tf].values():
                    if isinstance(sub_dict, dict) and key in sub_dict:
                        return sub_dict.get(key)
        return default

    def combine(self) -> Optional[Dict[str, Any]]:
        rule_based_signal = self.analytics.get("rule_based_signal", "HOLD")
        ai_signal = self.ai_confirmation.get("signal", "HOLD").upper()
        if ai_signal in ["N/A", "ERROR"]:
            ai_signal = "HOLD"

        final_signal = "HOLD"
        if rule_based_signal != "HOLD":
            is_contradictory = (rule_based_signal == "BUY" and ai_signal == "SELL") or \
                              (rule_based_signal == "SELL" and ai_signal == "BUY")
            if not is_contradictory:
                final_signal = rule_based_signal
        
        # اگر در نهایت سیگنالی برای معامله وجود نداشت، خروجی نده
        if final_signal == "HOLD":
            return None

        # --- اصلاح شد: پیدا کردن اولین استراتژی معتبر در میان تایم‌فریم‌ها ---
        strategy_data = {}
        primary_tf_with_strategy = None
        for tf in ['1h', '4h', '1d', '15m', '5m']:
            # .get("strategy", {}) برای جلوگیری از خطا اگر کلید strategy نبود
            current_strategy = self.details.get(tf, {}).get("strategy", {})
            if current_strategy: # اگر دیکشنری استراتژی خالی نبود
                strategy_data = current_strategy
                primary_tf_with_strategy = tf
                break # اولین مورد معتبر پیدا شد، از حلقه خارج شو

        # اگر هیچ‌کدام از تایم‌فریم‌ها استراتژی معتبری نداشتند، سیگنال را رد کن
        if not strategy_data:
            return None

        symbol = self._get_primary_data("symbol", "N/A")
        if symbol == "N/A":
            return None

        return {
            "symbol": symbol,
            "timeframe": primary_tf_with_strategy, # تایم‌فریمی که استراتژی از آن آمده
            "signal_type": final_signal,
            "current_price": strategy_data.get("entry_price"),
            "entry_zone": strategy_data.get("entry_zone", []),
            "targets": strategy_data.get("targets", []),
            "stop_loss": strategy_data.get("stop_loss"),
            "risk_reward_ratio": strategy_data.get("risk_reward_ratio"),
            "support_levels": strategy_data.get("support_levels", []),
            "resistance_levels": strategy_data.get("resistance_levels", []),
            "ai_confidence_percent": self.ai_confirmation.get("confidence", 0),
            "system_confidence_percent": round(abs(self.analytics.get("buy_score", 0) - self.analytics.get("sell_score", 0)) * 10, 2),
            "scores": {
                "buy_score": self.analytics.get("buy_score", 0),
                "sell_score": self.analytics.get("sell_score", 0),
            },
            "tags": self._get_primary_data("tags", []),
            "reasons": [self.ai_confirmation.get("reason")] if self.ai_confirmation.get("reason") else ["Score Based"],
            "issued_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            "raw_analysis_details": self.analytics
        }
