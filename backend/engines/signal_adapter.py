# engines/signal_adapter.py - نسخه نهایی و بی‌نقص

from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

class SignalAdapter:
    def __init__(self, analytics_output: Dict[str, Any], strategy: str = "balanced"):
        self.analytics = analytics_output or {}
        self.strategy = strategy.lower()
        self.ai_confirmation = self.analytics.get("gemini_confirmation", {})
        self.details = self.analytics.get("details", {})

    def _get_primary_detail(self, key: str, default: Any = "N/A"):
        """اطلاعات را از اولین تایم‌فریم معتبر استخراج می‌کند."""
        if not self.details:
            return default
        # اولویت با تایم‌فریم‌های بالاتر برای داده‌های کلیدی
        for tf in ['1d', '4h', '1h', '15m', '5m']:
            if tf in self.details and self.details[tf].get(key):
                return self.details[tf].get(key)
        return default

    def _get_strategy_data(self, key: str, default: Any = None):
        """اطلاعات را از خروجی موتور استراتژی استخراج می‌کند."""
        for tf in ['1d', '4h', '1h', '15m', '5m']:
             if tf in self.details and self.details[tf].get("strategy"):
                 if self.details[tf]["strategy"].get(key) is not None:
                     return self.details[tf]["strategy"].get(key)
        return default

    def combine(self) -> Dict[str, Any]:
        """تمام داده‌ها را به یک آبجکت سیگنال استاندارد و حرفه‌ای تبدیل می‌کند."""
        
        # استخراج داده‌های کلیدی با روش‌های قوی‌تر
        symbol = self._get_primary_detail("symbol")
        timeframe = next(iter(self.details)) if self.details else "multi-tf"
        rule_based_signal = self.analytics.get("rule_based_signal", "HOLD")
        
        # ترکیب سیگنال‌ها
        ai_signal = self.ai_confirmation.get("signal", "HOLD")
        votes = [s for s in [rule_based_signal, ai_signal] if s in ["BUY", "SELL", "HOLD"]]
        final_signal = "HOLD"
        if votes.count("BUY") > votes.count("SELL"):
            final_signal = "BUY"
        elif votes.count("SELL") > votes.count("BUY"):
            final_signal = "SELL"

        # استخراج دلایل و تگ‌ها
        reasons = []
        if rule_based_signal != "HOLD":
            reasons.append(f"Rule-based Score ({rule_based_signal})")
        if ai_signal != "HOLD" and ai_signal != "Error":
            reasons.append(f"AI Confirmation ({ai_signal})")
        
        tags = []
        for tf_data in self.details.values():
            if tf_data.get("trend", {}).get("breakout"):
                tags.append(f"{tf_data['interval']}_breakout")

        # ساخت آبجکت نهایی
        signal_obj = {
            "symbol": symbol,
            "timeframe": timeframe,
            "signal_type": final_signal,
            "current_price": self._get_strategy_data("entry_price", 0.0),
            "confidence": self.ai_confirmation.get("confidence", 0),
            "risk_level": self._get_primary_detail("risk_level", "unknown"),
            "scores": {
                "buy_score": self.analytics.get("buy_score"),
                "sell_score": self.analytics.get("sell_score"),
            },
            "strategy": {
                "entry_zone": self._get_strategy_data("entry_zone", []),
                "targets": self._get_strategy_data("targets", []),
                "stop_loss": self._get_strategy_data("stop_loss"),
                "risk_reward_ratio": self._get_strategy_data("risk_reward_ratio"),
            },
            "key_levels": {
                "support": self._get_strategy_data("support_levels", []),
                "resistance": self._get_strategy_data("resistance_levels", []),
            },
            "tags": list(set(tags)),
            "reasons": reasons,
            "issued_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        }
        return signal_obj
