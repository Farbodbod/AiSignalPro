# engines/signal_adapter.py (نسخه اصلاح شده)

from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

class SignalAdapter:
    # --- اصلاح شد: init به __init__ تغییر کرد ---
    def __init__(self, 
                 ai_output: Dict[str, Any], 
                 analytics_output: Dict[str, Any], 
                 signal_output: Optional[Dict[str, Any]] = None, 
                 strategy: str = "balanced"):
        self.ai = ai_output or {}
        self.analytics = analytics_output or {}
        self.signal = signal_output or {} # For potential future use
        self.strategy = strategy.lower()

    def get_vote(self, sig: Optional[str]) -> str:
        sig_upper = str(sig).upper()
        return sig_upper if sig_upper in ["BUY", "SELL", "HOLD"] else "HOLD"

    def calculate_confidence(self, ai_conf: float, an_conf: float) -> float:
        ai_conf = float(ai_conf or 0)
        an_conf = float(an_conf or 0)
        if self.strategy == "aggressive":
            return max(ai_conf, an_conf)
        elif self.strategy == "conservative":
            return min(ai_conf, an_conf)
        return round((ai_conf + an_conf) / 2, 3)

    def determine_signal(self, votes: List[str]) -> str:
        vote_count = {"BUY": 0, "SELL": 0, "HOLD": 0}
        for v in votes:
            vote_count[v] += 1

        if vote_count["BUY"] > vote_count["SELL"]:
            return "BUY"
        if vote_count["SELL"] > vote_count["BUY"]:
            return "SELL"
        return "HOLD"

    def risk_level_from_atr(self, atr: Optional[float], price: float) -> str:
        if atr is None or price is None or price == 0:
            return "unknown"
        ratio = atr / price
        if ratio > 0.06: return "high"
        elif ratio > 0.03: return "medium"
        return "low"

    def extract_tags(self) -> List[str]:
        tags = []
        if self.analytics.get('details'):
             for tf, data in self.analytics['details'].items():
                 if data.get('trend', {}).get('breakout'): tags.append(f"{tf}_breakout")
                 if data.get('trend', {}).get('fakeout'): tags.append(f"{tf}_fakeout")
                 if 'strong' in data.get('market_structure', {}).get('market_phase', ''): tags.append(f"{tf}_strong_trend")
        return sorted(set(tags))

    def combine(self) -> Dict[str, Any]:
        details = self.analytics.get("details", {})
        first_tf_key = next(iter(details)) if details else None
        first_tf_analytics = details.get(first_tf_key, {}) if first_tf_key else {}

        symbol = first_tf_analytics.get("symbol", "unknown")
        timeframe = first_tf_key or "multi"
        price = first_tf_analytics.get("indicators", {}).get("close", 0.0)
        atr = first_tf_analytics.get("indicators", {}).get("atr")

        votes = [
            self.get_vote(self.analytics.get("rule_based_signal")),
            self.get_vote(self.ai.get("signal")),
        ]
        final_signal = self.determine_signal(votes)

        confidence = self.ai.get("confidence", 50) # Use AI confidence as primary

        risk_level = self.risk_level_from_atr(atr, price)
        volatility_class = "volatile" if risk_level in ["medium", "high"] else "stable"

        signal_obj = {
            "id": f"{symbol}_{timeframe}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}",
            "symbol": symbol, "timeframe": timeframe,
            "signal_type": final_signal, "current_price": price,
            "confidence": confidence, "risk_level": risk_level,
            "volatility_class": volatility_class,
            "tags": self.extract_tags(),
            "issued_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            "strategy": self.strategy, "status": "active",
            "scores": {
                "buy_score": self.analytics.get("buy_score"),
                "sell_score": self.analytics.get("sell_score"),
            },
            "ai_provider_confirmation": self.ai,
            "raw_analysis_details": self.analytics.get("details")
        }
        return signal_obj

