from typing import Dict, Any
from datetime import datetime
import uuid

class SignalAdapter:
    def __init__(self, analytics_output: Dict[str, Any], **kwargs):
        self.analytics = analytics_output or {}
        self.ai_confirmation = self.analytics.get("gemini_confirmation", {})
        self.details = self.analytics.get("details", {})

    def _get_primary_data(self, key: str, default: Any = None):
        if not self.details: return default
        for tf in ['1h', '4h', '1d', '15m', '5m']:
            if tf in self.details and isinstance(self.details.get(tf), dict) and self.details[tf].get(key) is not None:
                return self.details[tf].get(key)
        return default

    def combine(self) -> Dict[str, Any]:
        rule_based_signal = self.analytics.get("rule_based_signal", "HOLD")
        ai_signal = self.ai_confirmation.get("signal", "HOLD")
        if ai_signal in ["N/A", "Error"]: ai_signal = "HOLD"
        final_signal = rule_based_signal if ai_signal == "HOLD" else ai_signal

        reasons = []
        if rule_based_signal != "HOLD":
            reasons.append(f"Score Signal ({self.analytics.get('buy_score', 0):.2f} vs {self.analytics.get('sell_score', 0):.2f})")
        if self.ai_confirmation.get("signal") not in ["N/A", "Error", "HOLD"]:
             reasons.append(f"AI Confirmed ({self.ai_confirmation.get('signal')})")
        
        strategy_data = self._get_primary_data("strategy", {}) or {}
        
        return {
            "symbol": self._get_primary_data("symbol", "N/A"),
            "timeframe": next(iter(self.details), "multi-tf"),
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
            "reasons": reasons or ["-"],
            "issued_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        }
