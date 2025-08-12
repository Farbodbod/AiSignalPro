import logging
from typing import Dict, Any, Optional, Tuple, List
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class VolumeCatalystPro(BaseStrategy):
    """
    VolumeCatalystPro - (v3.0 - Breakout Quality Score Edition)
    ------------------------------------------------------------------
    This world-class version evolves into a probability calculation machine. It uses
    a sophisticated "Breakout Quality Score" (BQS) engine to quantify the validity
    of a structural breakout by scoring its underlying volume, momentum, and volatility
    dynamics, while using an adaptive ATR-buffered stop loss.
    """
    strategy_name: str = "VolumeCatalystPro"

    # ✅ MIRACLE UPGRADE: Default configuration for the new BQS engine
    default_config = {
        "min_quality_score": 7,
        "weights": {
            "volume_catalyst_strength": 4,
            "momentum_thrust": 3,
            "volatility_release": 3,
        },
        "cci_threshold": 100.0,
        "atr_sl_multiplier": 1.0,
        "min_rr_ratio": 1.5,
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {
            "min_required_score": 2,
            "adx": {"weight": 1, "min_strength": 25},
            "supertrend": {"weight": 1}
        }
    }

    def _calculate_breakout_quality_score(self, direction: str, whales_data: Dict, cci_data: Dict, bollinger_data: Dict) -> tuple[int, List[str]]:
        """ ✅ New Helper: The Breakout Quality Score (BQS) Engine. """
        cfg = self.config
        weights = cfg.get('weights', {})
        score = 0
        confirmations = []

        # 1. Volume Catalyst Strength
        if whales_data['analysis'].get('is_whale_activity'):
            whale_pressure = whales_data['analysis'].get('pressure', '')
            if (direction == "BUY" and "Buying" in whale_pressure) or \
               (direction == "SELL" and "Selling" in whale_pressure):
                score += weights.get('volume_catalyst_strength', 4)
                spike_score = whales_data['analysis'].get('spike_score', 0)
                confirmations.append(f"Volume Catalyst (Score: {spike_score:.2f})")

        # 2. Momentum Thrust
        cci_value = cci_data.get('values', {}).get('value', 0)
        if (direction == "BUY" and cci_value > cfg.get('cci_threshold', 100.0)) or \
           (direction == "SELL" and cci_value < -cfg.get('cci_threshold', 100.0)):
            score += weights.get('momentum_thrust', 3)
            confirmations.append(f"Momentum Thrust (CCI: {cci_value:.2f})")

        # 3. Volatility Expansion / Squeeze Release
        if bollinger_data['analysis'].get('is_squeeze_release', False):
            score += weights.get('volatility_release', 3)
            confirmations.append("Volatility Release")
            
        return score, confirmations

    def _find_structural_breakout(self, structure_data: Dict) -> Optional[Tuple[str, float]]:
        # This helper remains largely the same, but now gets structure_data as input
        if self.df is None or len(self.df) < 2: return None, None
        prev_close = self.df['close'].iloc[-2]
        current_price = self.price_data.get('close')
        
        # We now use the detailed dictionary from our upgraded structure indicator
        prox_analysis = structure_data['analysis'].get('proximity', {})
        nearest_resistance = prox_analysis.get('nearest_resistance_details', {}).get('price')
        if nearest_resistance and prev_close <= nearest_resistance < current_price:
            return "BUY", nearest_resistance

        nearest_support = prox_analysis.get('nearest_support_details', {}).get('price')
        if nearest_support and prev_close >= nearest_support > current_price:
            return "SELL", nearest_support
        return None, None

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        if not self.price_data: return None
        
        # --- 1. Anti-Fragile Data Check ---
        indicators = {name: self.get_indicator(name) for name in ['structure', 'whales', 'cci', 'keltner_channel', 'bollinger', 'atr']}
        if not all(indicators.values()): return None

        # --- 2. Primary Trigger: Find a Structural Breakout ---
        signal_direction, broken_level = self._find_structural_breakout(indicators['structure'])
        if not signal_direction: return None
        
        # --- 3. Run the Breakout Quality Score Engine ---
        bqs, score_details = self._calculate_breakout_quality_score(signal_direction, indicators['whales'], indicators['cci'], indicators['bollinger'])
        
        if bqs < cfg.get('min_quality_score', 7): return None
            
        logger.info(f"[{self.strategy_name}] High-Quality Breakout: {signal_direction} with BQS {bqs}.")
        confirmations = {"breakout_quality_score": bqs, "score_details": ", ".join(score_details)}

        # --- 4. HTF Confirmation Filter ---
        if cfg['htf_confirmation_enabled']:
            if not self._get_trend_confirmation(signal_direction): return None
            confirmations['htf_filter'] = "Passed (HTF Aligned)"
        
        # --- 5. Adaptive Risk Management & Final Checks ---
        entry_price = self.price_data.get('close')
        keltner_mid = indicators['keltner_channel'].get('values', {}).get('middle_band')
        atr_value = indicators['atr'].get('values', {}).get('atr')
        if not all([entry_price, keltner_mid, atr_value]): return None
        
        # ATR-Buffered Stop Loss
        stop_loss = keltner_mid - (atr_value * cfg.get('atr_sl_multiplier', 1.0)) if signal_direction == "BUY" else keltner_mid + (atr_value * cfg.get('atr_sl_multiplier', 1.0))
            
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        
        if not risk_params or risk_params.get("risk_reward_ratio", 0) < cfg.get('min_rr_ratio', 1.5):
            return None
        confirmations['rr_check'] = f"Passed (R/R: {risk_params.get('risk_reward_ratio', 0):.2f})"
        
        logger.info(f"✨✨ [{self.strategy_name}] VOLUME CATALYST SIGNAL CONFIRMED! ✨✨")

        return { "direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations }
