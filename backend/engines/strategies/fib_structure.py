import logging
from typing import Dict, Any, Optional, List
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class ConfluenceSniper(BaseStrategy):
    """
    ConfluenceSniper - (v3.0 - Confluence Scoring Edition)
    -------------------------------------------------------------------
    This world-class version evolves from a simple filter funnel to a sophisticated
    "Confluence Score" engine. It quantifies the quality of a reversal setup at
    a key PRZ by weighting confirmations from oscillators, candlesticks, and volume,
    while using an adaptive risk framework.
    """
    strategy_name: str = "ConfluenceSniper"
    
    # ✅ MIRACLE UPGRADE: Default configuration using the new BaseStrategy v4.0 features
    default_config = {
        "fib_levels_to_watch": ["61.8%", "78.6%"],
        "confluence_proximity_percent": 0.3,
        "min_confluence_score": 5,
        "weights": {
            "dual_oscillator": 3,
            "single_oscillator": 1,
            "candlestick": 2,
            "climactic_volume": 3
        },
        "volatility_regimes": {
            "low_atr_pct_threshold": 1.5,
            "low_vol_sl_multiplier": 1.2,
            "high_vol_sl_multiplier": 1.8
        },
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {
            "min_required_score": 1,
            "adx": {"weight": 1, "min_strength": 25}
        }
    }

    def _calculate_confluence_score(self, direction: str, rsi_data: Dict, stoch_data: Dict, whales_data: Dict) -> tuple[int, List[str]]:
        """ ✅ New Helper: The Confluence Score Engine. """
        weights = self.config.get('weights', {})
        score = 0
        confirmations = []

        # Oscillator Confirmation Scoring
        rsi_confirm, stoch_confirm = self._get_oscillator_confirmation(direction, rsi_data, stoch_data)
        if rsi_confirm and stoch_confirm:
            score += weights.get('dual_oscillator', 3)
            confirmations.append("Dual Oscillator Confirmation")
        elif rsi_confirm or stoch_confirm:
            score += weights.get('single_oscillator', 1)
            confirmations.append("Single Oscillator Confirmation")
        
        # Candlestick Confirmation
        if self._get_candlestick_confirmation(direction, min_reliability='Strong'):
            score += weights.get('candlestick', 2)
            confirmations.append("Strong Candlestick Pattern")
        
        # Volume Climax Confirmation
        if whales_data['analysis'].get('is_climactic_volume', False):
            score += weights.get('climactic_volume', 3)
            confirmations.append("Climactic Volume")
            
        return score, confirmations

    def _get_oscillator_confirmation(self, direction: str, rsi_data: Dict, stoch_data: Dict) -> tuple[bool, bool]:
        """ Checks RSI and Stochastic and returns a tuple of booleans. """
        rsi_confirm, stoch_confirm = False, False
        
        rsi_val = rsi_data.get('values', {}).get('rsi')
        stoch_pos = stoch_data.get('analysis', {}).get('position')
        
        if rsi_val is not None:
            rsi_os = rsi_data.get('levels', {}).get('oversold', 30)
            rsi_ob = rsi_data.get('levels', {}).get('overbought', 70)
            if direction == "BUY" and rsi_val < rsi_os: rsi_confirm = True
            elif direction == "SELL" and rsi_val > rsi_ob: rsi_confirm = True

        if stoch_pos is not None:
            if direction == "BUY" and stoch_pos == 'Oversold': stoch_confirm = True
            elif direction == "SELL" and stoch_pos == 'Overbought': stoch_confirm = True
            
        return rsi_confirm, stoch_confirm

    def _find_best_prz(self, cfg: Dict, fib_data: Dict, structure_data: Dict) -> Optional[Dict]:
        # This helper remains largely the same
        current_price = self.price_data.get('close')
        if not current_price: return None
        fib_levels = {lvl['level']: lvl['price'] for lvl in fib_data.get('levels', []) if 'Retracement' in lvl['type']}
        key_levels = structure_data.get('key_levels', {})
        swing_trend = fib_data.get('swing_trend')
        target_sr_zones = key_levels.get('supports' if swing_trend == "Up" else 'resistances', [])
        confluence_zones = []
        for fib_level_str in cfg['fib_levels_to_watch']:
            fib_price = fib_levels.get(fib_level_str)
            if not fib_price: continue
            for sr_zone in target_sr_zones:
                sr_price = sr_zone.get('price')
                if sr_price and abs(fib_price - sr_price) / sr_price * 100 < cfg['confluence_proximity_percent']:
                    zone_price = (fib_price + sr_price) / 2.0
                    confluence_zones.append({ "price": zone_price, "fib_level": fib_level_str, "structure_zone": sr_zone, "distance_to_price": abs(zone_price - current_price) })
        return min(confluence_zones, key=lambda x: x['distance_to_price']) if confluence_zones else None

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        if not self.price_data: return None

        indicators = {name: self.get_indicator(name) for name in ['fibonacci', 'structure', 'rsi', 'stochastic', 'atr', 'patterns', 'whales']}
        if not all(indicators.values()): return None

        swing_trend = indicators['fibonacci'].get('swing_trend')
        direction = "BUY" if swing_trend == "Up" else "SELL" if swing_trend == "Down" else None
        if not direction: return None

        best_prz = self._find_best_prz(cfg, indicators['fibonacci'], indicators['structure'])
        if not best_prz: return None

        price_low, price_high = self.price_data.get('low'), self.price_data.get('high')
        is_testing = (direction == "BUY" and price_low and price_low <= best_prz['price']) or \
                     (direction == "SELL" and price_high and price_high >= best_prz['price'])
        if not is_testing: return None
        
        # --- ✅ MIRACLE UPGRADE: Run the Confluence Scoring Engine ---
        confluence_score, score_details = self._calculate_confluence_score(direction, indicators['rsi'], indicators['stochastic'], indicators['whales'])
        
        if confluence_score < cfg.get('min_confluence_score', 5): return None

        confirmations = {"confluence_score": confluence_score, "score_details": ", ".join(score_details)}
        
        # HTF Filter
        if cfg['htf_confirmation_enabled']:
            opposite_direction = "SELL" if direction == "BUY" else "BUY"
            if self._get_trend_confirmation(opposite_direction): return None
            confirmations['htf_filter'] = "Passed (No strong opposing trend)"

        # --- ✅ MIRACLE UPGRADE: Adaptive Risk Management ---
        entry_price = self.price_data.get('close')
        if not entry_price: return None
        
        vol_cfg = cfg.get('volatility_regimes', {})
        atr_pct = indicators['atr'].get('values', {}).get('atr_percent', 2.0)
        is_low_vol = atr_pct < vol_cfg.get('low_atr_pct_threshold', 1.5)
        atr_sl_multiplier = vol_cfg.get('low_vol_sl_multiplier', 1.2) if is_low_vol else vol_cfg.get('high_vol_sl_multiplier', 1.8)
        
        atr_value = indicators['atr'].get('values', {}).get('atr', entry_price * 0.01)
        structure_level = best_prz['structure_zone']['price']
        
        stop_loss = structure_level - (atr_value * atr_sl_multiplier) if direction == "BUY" else structure_level + (atr_value * atr_sl_multiplier)
            
        risk_params = self._calculate_smart_risk_management(entry_price, direction, stop_loss)
        if not risk_params or not risk_params.get("targets"): return None
        confirmations['rr_check'] = f"Passed (R/R: {risk_params.get('risk_reward_ratio')})"

        logger.info(f"✨✨ [{self.strategy_name}] CONFLUENCE SNIPER SIGNAL CONFIRMED! ✨✨")
        
        return { "direction": direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations }

