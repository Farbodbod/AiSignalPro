import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class KeltnerMomentumBreakout(BaseStrategy):
    """
    KeltnerMomentumBreakout - (v3.0 - Momentum Scoring Edition)
    -------------------------------------------------------------------------
    This world-class version evolves from a simple filter funnel to a sophisticated
    "Momentum Power Score" engine. It quantifies the quality of a Keltner breakout
    by weighting confirmations from trend strength (ADX) and momentum thrust (CCI),
    while using an adaptive risk framework.
    """
    strategy_name: str = "KeltnerMomentumBreakout"

    # ✅ MIRACLE UPGRADE: Default configuration for the new engines
    default_config = {
        "min_momentum_score": 4,
        "weights": {
            "adx_strength": 2,
            "cci_thrust": 3,
            "htf_alignment": 2,
            "candlestick": 1
        },
        "adx_threshold": 25.0,
        "cci_threshold": 100.0,
        "volatility_regimes": {
            "low_atr_pct_threshold": 1.5,
            "low_vol_sl_multiplier": 1.0, # Tighter stop in low vol
            "high_vol_sl_multiplier": 1.5 # Wider stop in high vol
        },
        "candlestick_confirmation_enabled": True,
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {
            "min_required_score": 2,
            "adx": {"weight": 1, "min_strength": 25},
            "supertrend": {"weight": 1}
        }
    }

    def _calculate_momentum_score(self, direction: str, adx_data: Dict, cci_data: Dict) -> tuple[int, List[str]]:
        """ ✅ New Helper: The Momentum Power Score Engine. """
        cfg = self.config
        weights = cfg.get('weights', {})
        score = 0
        confirmations = []

        # 1. ADX Strength Confirmation
        adx_strength = adx_data.get('values', {}).get('adx', 0)
        if adx_strength >= cfg.get('adx_threshold', 25.0):
            score += weights.get('adx_strength', 2)
            confirmations.append(f"ADX Strength ({adx_strength:.2f})")

        # 2. CCI Momentum Thrust Confirmation
        cci_value = cci_data.get('values', {}).get('value', 0)
        cci_threshold = cfg.get('cci_threshold', 100.0)
        if (direction == "BUY" and cci_value > cci_threshold) or \
           (direction == "SELL" and cci_value < -cci_threshold):
            score += weights.get('cci_thrust', 3)
            confirmations.append(f"CCI Thrust ({cci_value:.2f})")

        # 3. HTF Alignment Confirmation
        if cfg.get('htf_confirmation_enabled'):
            if self._get_trend_confirmation(direction):
                score += weights.get('htf_alignment', 2)
                confirmations.append("HTF Aligned")

        # 4. Candlestick Confirmation
        if cfg.get('candlestick_confirmation_enabled'):
            if self._get_candlestick_confirmation(direction, min_reliability='Medium'):
                score += weights.get('candlestick', 1)
                confirmations.append("Candlestick Confirmed")
        
        return score, confirmations

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        if not self.price_data: return None
        
        # --- 1. Anti-Fragile Data Check ---
        indicators = {name: self.get_indicator(name) for name in ['keltner_channel', 'adx', 'cci', 'atr']}
        if not all(indicators.values()): return None

        # --- 2. Primary Trigger: Keltner Channel Breakout ---
        keltner_data = indicators['keltner_channel']
        keltner_pos = keltner_data.get('analysis', {}).get('position')
        signal_direction = None
        if "Breakout Above" in keltner_pos: signal_direction = "BUY"
        elif "Breakdown Below" in keltner_pos: signal_direction = "SELL"
        else: return None
        
        # --- 3. Run the Momentum Power Score Engine ---
        momentum_score, score_details = self._calculate_momentum_score(signal_direction, indicators['adx'], indicators['cci'])
        
        if momentum_score < cfg.get('min_momentum_score', 4):
            return None
            
        logger.info(f"[{self.strategy_name}] High-Quality Momentum Breakout: {signal_direction} with Power Score {momentum_score}.")
        confirmations = {"power_score": momentum_score, "score_details": ", ".join(score_details)}

        # --- 4. Adaptive Risk Management & Final Checks ---
        entry_price = self.price_data.get('close')
        if not entry_price: return None
        
        # Stop loss is placed on the Keltner Channel's middle line (EMA)
        stop_loss = keltner_data.get('values', {}).get('middle_band')
        if not stop_loss: return None
            
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        
        if not risk_params or not risk_params.get("targets"):
            return None
        confirmations['rr_check'] = f"Passed (R/R: {risk_params.get('risk_reward_ratio')})"
        
        logger.info(f"✨✨ [{self.strategy_name}] KELTNER MOMENTUM SIGNAL CONFIRMED! ✨✨")

        # --- 5. Package and Return the Enriched Signal ---
        return {
            "direction": signal_direction,
            "entry_price": entry_price,
            **risk_params,
            "confirmations": confirmations
        }
