# engines/signal_adapter.py (نسخه نهایی با منطق ترکیب سیگنال اصلاح شده)

from typing import Dict, Any, Optional
from datetime import datetime
import uuid

class SignalAdapter:
    def __init__(self, analytics_output: Dict[str, Any], **kwargs):
        self.analytics = analytics_output or {}
        self.ai_confirmation = self.analytics.get("gemini_confirmation", {})
        self.details = self.analytics.get("details", {})

    def _get_primary_data(self, key: str, default: Any = None, timeframe_priority: list = None):
        """از تایم فریم اصلی داده‌ها را استخراج می‌کند."""
        if not self.details: return default
        if timeframe_priority is None:
            timeframe_priority = ['1h', '4h', '1d', '15m', '5m']
        
        for tf in timeframe_priority:
            if tf in self.details and isinstance(self.details.get(tf), dict):
                # اگر کلید اصلی وجود داشت
                if key in self.details[tf] and self.details[tf].get(key) is not None:
                    return self.details[tf][key]
                # اگر کلید در دیکشنری تو در تو (مثل strategy) بود
                for sub_dict in self.details[tf].values():
                    if isinstance(sub_dict, dict) and key in sub_dict:
                        return sub_dict[key]
        return default

    def combine(self) -> Optional[Dict[str, Any]]:
        rule_based_signal = self.analytics.get("rule_based_signal", "HOLD")
        ai_signal = self.ai_confirmation.get("signal", "HOLD").upper()
        if ai_signal in ["N/A", "ERROR"]: ai_signal = "HOLD"

        # ## --- اصلاح شد: منطق جدید و امن‌تر ترکیب سیگنال --- ##
        final_signal = "HOLD"
        if rule_based_signal != "HOLD":
            # اگر AI مخالف بود، سیگنال را وتو کن و HOLD کن
            if (rule_based_signal == "BUY" and ai_signal == "SELL") or \
               (rule_based_signal == "SELL" and ai_signal == "BUY"):
                final_signal = "HOLD" 
            else: # اگر AI موافق یا بی‌نظر بود، به سیگنال اصلی اعتماد کن
                final_signal = rule_based_signal

        # --- استخراج داده‌های استراتژی از تایم‌فریم اصلی (1h) ---
        primary_tf = next(iter(self.details), '1h')
        strategy_data = self.details.get(primary_tf, {}).get("strategy", {})
        if not strategy_data:
            return None # اگر استراتژی وجود نداشت، سیگنال معتبر نیست

        symbol = self._get_primary_data("symbol", "N/A")
        if symbol == "N/A": return None # اگر نماد مشخص نبود، سیگنال معتبر نیست

        return {
            "symbol": symbol,
            "timeframe": primary_tf,
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
            "raw_analysis_details": self.analytics # داده خام برای ذخیره در دیتابیس
        }
