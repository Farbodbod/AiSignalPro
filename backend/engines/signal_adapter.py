from typing import Dict, Any, List
from datetime import datetime
import uuid

class SignalAdapter:
    def __init__(self, analytics_output: Dict[str, Any], strategy: str = "balanced"):
        self.analytics = analytics_output or {}
        self.strategy = strategy.lower()
        self.ai_confirmation = self.analytics.get("gemini_confirmation", {})
        self.details = self.analytics.get("details", {})

    def _get_primary_detail(self, key: str, default: Any = "N/A"):
        if not self.details: return default
        for tf in ['1d', '4h', '1h', '15m', '5m']:
            if tf in self.details and self.details[tf].get(key):
                return self.details[tf].get(key)
        return default

    def _get_strategy_data(self, key: str, default: Any = None):
        if not self.details: return default
        for tf in ['1d', '4h', '1h', '15m', '5m']:
             if tf in self.details and self.details[tf].get("strategy"):
                 if self.details[tf]["strategy"].get(key) is not None:
                     return self.details[tf]["strategy"].get(key)
        return default

    def combine(self) -> Dict[str, Any]:
        symbol = self._get_primary_detail("symbol")
        timeframe = next(iter(self.details)) if self.details else "multi-tf"
        rule_based_signal = self.analytics.get("rule_based_signal", "HOLD")
        
        ai_signal = self.ai_confirmation.get("signal", "HOLD")
        if ai_signal in ["N/A", "Error"]: ai_signal = "HOLD"
        
        votes = [rule_based_signal, ai_signal]
        final_signal = "HOLD"
        if votes.count("BUY") > votes.count("SELL"): final_signal = "BUY"
        elif votes.count("SELL") > votes.count("BUY"): final_signal = "SELL"

        reasons = []
        if rule_based_signal != "HOLD": reasons.append(f"Rule-based Score ({rule_based_signal})")
        if ai_signal != "HOLD": reasons.append(f"AI Confirmation ({ai_signal})")
        
        tags = []
        for tf_data in self.details.values():
            if tf_data.get("trend", {}).get("breakout"): tags.append(f"{tf_data.get('interval', '')}_breakout")

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
