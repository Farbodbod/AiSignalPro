from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

class SignalAdapter:
    def __init__(self, analytics_output: Dict[str, Any], strategy: str = "balanced"):
        self.analytics = analytics_output or {}
        self.strategy = strategy.lower()
        self.ai_confirmation = self.analytics.get("gemini_confirmation", {})

    def _extract_from_details(self, key: str, data_key: str, default: Any = None):
        """از جزئیات مولتی-تایم‌فریم، اطلاعات را استخراج می‌کند."""
        details = self.analytics.get("details", {})
        if not details: return default
        # اولویت با تایم‌فریم‌های بالاتر است
        for tf in ['1d', '4h', '1h', '15m', '5m']:
            if tf in details and details[tf].get(key) and data_key in details[tf][key]:
                return details[tf][key][data_key]
        return default

    def _extract_strategy_data(self, key: str, default: Any = None):
        """اطلاعات را از خروجی موتور استراتژی استخراج می‌کند."""
        # استراتژی فقط روی تایم فریم های اصلی اجرا می شود
        details = self.analytics.get("details", {})
        if not details: return default
        for tf in ['1d', '4h', '1h']:
             if tf in details and details[tf].get("strategy"):
                 return details[tf]["strategy"].get(key, default)
        return default


    def combine(self) -> Dict[str, Any]:
        details = self.analytics.get("details", {})
        first_tf_key = next(iter(details)) if details else "N/A"
        
        # استخراج دلایل سیگنال
        reasons = []
        rule_based_signal = self.analytics.get("rule_based_signal", "HOLD")
        if rule_based_signal != "HOLD":
            reasons.append(f"Rule-based score consensus ({rule_based_signal})")
        if self.ai_confirmation.get("signal") == rule_based_signal:
            reasons.append(f"AI ({self.ai_confirmation.get('signal')}) confirmed the signal")
        if self._extract_from_details("trend", "breakout", False):
            reasons.append("Potential breakout detected")
        
        # خروجی نهایی و حرفه‌ای
        signal_obj = {
            "id": f"{self._extract_from_details('symbol', 'N/A')}_{first_tf_key}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            "symbol": self._extract_from_details('symbol', 'N/A'),
            "timeframe": first_tf_key,
            "signal_type": rule_based_signal,
            "current_price": self._extract_strategy_data("entry_price"),
            "entry_zone": [
                round(self._extract_strategy_data("entry_price", 0) * 0.998, 4),
                round(self._extract_strategy_data("entry_price", 0) * 1.002, 4)
            ],
            "targets": self._extract_strategy_data("targets", []),
            "stop_loss": self._extract_strategy_data("stop_loss"),
            "risk_reward_ratio": self._extract_strategy_data("risk_reward_ratio"),
            "support_levels": self._extract_strategy_data("support_levels", []),
            "resistance_levels": self._extract_strategy_data("resistance_levels", []),
            "ai_confidence_percent": self.ai_confirmation.get("confidence"),
            "system_confidence_percent": round(
                abs(self.analytics.get("buy_score", 0) - self.analytics.get("sell_score", 0)) * 10, 2
            ),
            "signal_reasons": reasons,
            "issued_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        }
        return signal_obj
