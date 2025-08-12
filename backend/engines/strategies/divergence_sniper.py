import logging
from typing import Dict, Any, Optional, List
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class DivergenceSniperPro(BaseStrategy):
    """
    DivergenceSniperPro - (v3.0 - Exhaustion & Climax Engine)
    -----------------------------------------------------------------------
    This world-class version operates as a high-precision reversal sniper.
    It combines three advanced pillars for signal validation:
    1.  Fortress S/R Engine: Only considers divergences at high-strength S/R zones.
    2.  Climactic Volume Detector: Confirms trend exhaustion with climactic volume spikes.
    3.  Adaptive Volatility Framework: Adjusts risk parameters based on market volatility.
    """
    strategy_name: str = "DivergenceSniperPro"

    # ✅ MIRACLE UPGRADE: Default configuration using the new BaseStrategy v4.0 features
    default_config = {
        "volume_confirmation_enabled": True,
        "candlestick_confirmation_enabled": True,
        # Pillar 1: Fortress S/R Engine config
        "min_structure_strength": 3, # e.g., requires at least 3 historical touches
        # Pillar 3: Adaptive Volatility Framework config
        "volatility_regimes": {
            "low_atr_pct_threshold": 1.5, # Below this is considered low volatility
            "low_vol_sl_multiplier": 1.0,
            "high_vol_sl_multiplier": 1.5
        },
        # HTF Engine config
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {
            "min_required_score": 1,
            "adx": {"weight": 1, "min_strength": 25}
        }
    }
    
    def _confirm_fortress_sr(self, direction: str, structure_data: Dict) -> Optional[Dict[str, Any]]:
        """ ✅ New Helper: Confirms the divergence is at a high-strength, tested S/R zone. """
        min_strength = self.config.get("min_structure_strength", 3)
        prox_data = structure_data.get('analysis', {}).get('proximity', {})
        
        zone_details = None
        if direction == "BUY":
            if prox_data.get('is_testing_support'):
                zone_details = prox_data.get('nearest_support_details')
        elif direction == "SELL":
            if prox_data.get('is_testing_resistance'):
                zone_details = prox_data.get('nearest_resistance_details')
        
        if zone_details and zone_details.get('strength', 0) >= min_strength:
            return zone_details # Return the details of the confirmed zone
        return None

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        
        # --- 1. Anti-Fragile Data Check ---
        if not self.price_data: return None
        
        required_indicators = ['divergence', 'structure', 'williams_r', 'atr', 'whales', 'patterns']
        indicators = {name: self.get_indicator(name) for name in required_indicators}
        if not all(indicators.values()):
            return None

        # --- 2. Find a Valid Divergence Signal ---
        divergence_data = indicators['divergence']
        if not divergence_data.get('analysis', {}).get('signals'): return None
        potential_signals = [s for s in divergence_data['analysis']['signals'] if "Regular" in s.get('type', '')]
        if not potential_signals: return None
        divergence = potential_signals[0]
        signal_direction = "BUY" if "Bullish" in divergence['type'] else "SELL"
        
        # --- 3. MIRACLE CONFIRMATION FUNNEL ---
        confirmations = {"divergence_type": divergence['type']}

        # ✅ Pillar 1: Fortress S/R Confirmation
        fortress_zone = self._confirm_fortress_sr(signal_direction, indicators['structure'])
        if not fortress_zone:
            return None
        confirmations['structure_filter'] = f"Passed (Fortress S/R Zone Strength: {fortress_zone.get('strength')})"
        
        # ✅ Pillar 2: Climactic Volume Confirmation
        if cfg.get('volume_confirmation_enabled'):
            if not indicators['whales']['analysis'].get('is_climactic_volume', False):
                return None
            confirmations['volume_filter'] = "Passed (Climactic Volume Detected)"

        # HTF Filter (using new engine)
        if cfg.get('htf_confirmation_enabled'):
            opposite_direction = "SELL" if signal_direction == "BUY" else "BUY"
            if self._get_trend_confirmation(opposite_direction):
                return None
            confirmations['htf_filter'] = "Passed (No strong opposing trend)"

        # Candlestick Filter
        if cfg.get('candlestick_confirmation_enabled'):
            confirming_pattern = self._get_candlestick_confirmation(signal_direction, min_reliability='Strong')
            if not confirming_pattern: return None
            confirmations['candlestick_filter'] = f"Passed (Pattern: {confirming_pattern.get('name')})"

        # Final Trigger: Williams %R
        wr_signal = indicators['williams_r'].get('analysis', {}).get('crossover_signal', 'Hold')
        trigger_fired = (signal_direction == "BUY" and "Buy" in wr_signal) or \
                        (signal_direction == "SELL" and "Sell" in wr_signal)
        if not trigger_fired: return None
        confirmations['momentum_trigger'] = "Passed (Williams %R Crossover)"

        logger.info(f"✨✨ [{self.strategy_name}] DIVERGENCE SNIPER SIGNAL CONFIRMED! ✨✨")

        # --- ✅ Pillar 3: Adaptive Risk Management ---
        entry_price = self.price_data.get('close')
        atr_data = indicators['atr']
        if not entry_price: return None
        
        # Determine volatility regime to select the correct SL multiplier
        vol_cfg = cfg.get('volatility_regimes', {})
        atr_pct = atr_data.get('values', {}).get('atr_percent', 2.0)
        is_low_vol = atr_pct < vol_cfg.get('low_atr_pct_threshold', 1.5)
        
        atr_sl_multiplier = vol_cfg.get('low_vol_sl_multiplier', 1.0) if is_low_vol else vol_cfg.get('high_vol_sl_multiplier', 1.5)
        confirmations['volatility_context'] = f"Adaptive SL Multiplier: x{atr_sl_multiplier} ({'Low' if is_low_vol else 'High'} Vol)"
        
        pivot_price = divergence.get('pivots', [{}, {}])[1].get('price')
        if not pivot_price: return None
        atr_value = atr_data.get('values', {}).get('atr', entry_price * 0.01)
        
        if signal_direction == "BUY": stop_loss = pivot_price - (atr_value * atr_sl_multiplier)
        else: stop_loss = pivot_price + (atr_value * atr_sl_multiplier)

        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        if not risk_params or not risk_params.get("targets"): return None
        
        return { "direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations }
