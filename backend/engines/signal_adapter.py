from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid

class SignalAdapter:
    def __init__(self, analytics_output: Dict[str, Any], **kwargs):
        self.analytics = analytics_output or {}
        self.ai_confirmation = self.analytics.get("gemini_confirmation", {})
        self.details = self.analytics.get("details", {})

    def _get_primary_data(self, key: str, default: Any = None):
        if not self.details:
            return default
        for tf in ['1h', '4h', '1d', '15m', '5m']:
            if tf in self.details and isinstance(self.details.get(tf), dict):
                if key in self.details[tf] and self.details[tf].get(key) is not None:
                    return self.details[tf][key]
                for sub_dict in self.details[tf].values():
                    if isinstance(sub_dict, dict) and key in sub_dict:
                        return sub_dict.get(key)
        return default

    def _aggregate_reasons(self) -> List[str]:
        reasons = set()
        for tf, analysis in self.details.items():
            if not isinstance(analysis, dict):
                continue
            if "Uptrend" in analysis.get('trend', {}).get('signal', ''):
                reasons.add(f"Uptrend on {tf}")
            if "Downtrend" in analysis.get('trend', {}).get('signal', ''):
                reasons.add(f"Downtrend on {tf}")
            if analysis.get('divergence', {}).get('rsi_bullish'):
                reasons.add(f"Bullish RSI Divergence on {tf}")
            if analysis.get('divergence', {}).get('rsi_bearish'):
                reasons.add(f"Bearish RSI Divergence on {tf}")
            whale_activity = analysis.get('whale_activity', {}).get('type') or analysis.get('whale_activity', {}).get('activity')
            if whale_activity == 'volume_spike':
                reasons.add(f"Whale Volume Spike on {tf}")
            if whale_activity == 'anomaly':
                reasons.add(f"Whale Anomaly Detected on {tf}")
            for pattern in analysis.get('patterns', []):
                reasons.add(f"{pattern} on {tf}")
        return sorted(list(reasons))

    def _determine_final_signal(self) -> str:
        rule_based_signal = self.analytics.get("rule_based_signal", "HOLD")
        ai_signal = self.ai_confirmation.get("signal", "HOLD").upper()
        if ai_signal in ["N/A", "ERROR"]:
            ai_signal = "HOLD"
        if rule_based_signal == "HOLD":
            return "HOLD"
        is_contradictory = (
            (rule_based_signal == "BUY" and ai_signal == "SELL") or
            (rule_based_signal == "SELL" and ai_signal == "BUY")
        )
        return "HOLD" if is_contradictory else rule_based_signal

    def generate_final_signal(self) -> Optional[Dict[str, Any]]:
        final_signal = self._determine_final_signal()
        if final_signal == "HOLD":
            return None

        strategy_data, primary_tf_with_strategy = {}, None
        for tf in ['1h', '4h', '1d', '15m', '5m']:
            current_strategy = self.details.get(tf, {}).get("strategy", {})
            if current_strategy:
                strategy_data = current_strategy
                primary_tf_with_strategy = tf
                break

        if not strategy_data:
            return None

        symbol = self._get_primary_data("symbol", "N/A")
        if symbol == "N/A":
            return None

        aggregated_reasons = self._aggregate_reasons()

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
            "ai_confidence_percent": self.ai_confirmation.get("confidence", 0),
            "system_confidence_percent": round(abs(self.analytics.get("buy_score", 0) - self.analytics.get("sell_score", 0)) * 10, 2),
            "reasons": aggregated_reasons or ["Score Based Analysis"],
            "explanation_fa": self.ai_confirmation.get("explanation_fa", "توضیحات AI در دسترس نیست."),
            "issued_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            "timeframes_analyzed": list(self.details.keys())
        }

        return final_payload
