# engines/signal_adapter.py (نسخه نهایی با دلایل کامل و دقیق)

from typing import Dict, Any, Optional, List
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
            if tf in self.details and isinstance(self.details.get(tf), dict):
                if key in self.details[tf] and self.details[tf].get(key) is not None:
                    return self.details[tf][key]
                for sub_dict in self.details[tf].values():
                    if isinstance(sub_dict, dict) and key in sub_dict:
                        return sub_dict.get(key)
        return default

    ## --- تابع جدید برای استخراج تمام دلایل --- ##
    def _aggregate_reasons(self) -> List[str]:
        """
        تمام تحلیل‌های خام را بررسی کرده و لیستی از دلایل قابل فهم تولید می‌کند.
        """
        reasons = set() # استفاده از set برای جلوگیری از دلایل تکراری
        
        for tf, analysis in self.details.items():
            if not isinstance(analysis, dict): continue

            # ۱. دلایل از تحلیل روند (Trend)
            trend_info = analysis.get('trend', {})
            if "Strong Uptrend" in trend_info.get('signal', ''):
                reasons.add(f"Strong Uptrend on {tf}")
            if "Strong Downtrend" in trend_info.get('signal', ''):
                reasons.add(f"Strong Downtrend on {tf}")

            # ۲. دلایل از الگوهای کندلی (Candlestick Patterns)
            # فرض می‌کنیم موتور تحلیل کندل، لیستی از الگوها را در کلید 'patterns' برمی‌گرداند
            patterns = analysis.get('patterns', [])
            for pattern in patterns:
                if 'Bullish' in pattern:
                    reasons.add(f"{pattern} on {tf}")
                elif 'Bearish' in pattern:
                    reasons.add(f"{pattern} on {tf}")

            # ۳. دلایل از واگرایی‌ها (Divergences)
            # فرض می‌کنیم موتور واگرایی، دیکشنری در کلید 'divergence' برمی‌گرداند
            divergence = analysis.get('divergence', {})
            if divergence.get('rsi_bullish'):
                reasons.add(f"Bullish RSI Divergence on {tf}")
            if divergence.get('rsi_bearish'):
                reasons.add(f"Bearish RSI Divergence on {tf}")

            # ۴. دلایل از ساختار بازار (Market Structure - Pivots)
            market_structure = analysis.get('market_structure', {})
            if market_structure.get('phase') == 'Bullish Break of Structure':
                 reasons.add(f"Break of Structure Upwards on {tf}")
            if market_structure.get('phase') == 'Bearish Break of Structure':
                 reasons.add(f"Break of Structure Downwards on {tf}")

        return sorted(list(reasons))


    def combine(self) -> Optional[Dict[str, Any]]:
        rule_based_signal = self.analytics.get("rule_based_signal", "HOLD")
        ai_signal = self.ai_confirmation.get("signal", "HOLD").upper()
        if ai_signal in ["N/A", "ERROR"]: ai_signal = "HOLD"

        final_signal = "HOLD"
        if rule_based_signal != "HOLD":
            is_contradictory = (rule_based_signal == "BUY" and ai_signal == "SELL") or \
                              (rule_based_signal == "SELL" and ai_signal == "BUY")
            if not is_contradictory:
                final_signal = rule_based_signal
        
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
        if symbol == "N/A": return None

        # ## --- بهبود یافته: ترکیب دلایل --- ##
        aggregated_reasons = self._aggregate_reasons()
        if self.ai_confirmation.get("reason"):
             # دلیل AI را برای اهمیت بیشتر، در ابتدا قرار می‌دهیم
            aggregated_reasons.insert(0, f"AI: {self.ai_confirmation['reason']}")

        return {
            "symbol": symbol,
            "timeframe": primary_tf_with_strategy,
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
            "scores": {"buy_score": self.analytics.get("buy_score", 0), "sell_score": self.analytics.get("sell_score", 0)},
            "tags": self._get_primary_data("tags", []),
            "reasons": aggregated_reasons or ["Score Based Analysis"],
            "issued_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            "raw_analysis_details": self.analytics
        }
