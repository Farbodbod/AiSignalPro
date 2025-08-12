import logging
from typing import Dict, Any, Optional, List
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class PivotConfluenceSniper(BaseStrategy):
    """
    PivotConfluenceSniper - (v3.0 - Adaptive Confluence Engine)
    ----------------------------------------------------------------------------
    This world-class version evolves into an adaptive special operations commander. It features:
    1.  Timeframe-Aware Intelligence: Uses different parameters for different timeframes.
    2.  Advanced HTF Context Engine: Intelligently gauges the strength of opposing trends.
    3.  Multi-Target Profit System: Sets tactical and strategic profit targets.
    """
    strategy_name: str = "PivotConfluenceSniper"

    # ✅ MIRACLE UPGRADE: Hierarchical configuration for timeframe adaptability
    default_config = {
        "default_params": {
            "pivot_levels_to_check": ["R2", "R1", "S1", "S2"],
            "confluence_proximity_percent": 0.3,
            "stoch_oversold": 25.0, "stoch_overbought": 75.0,
            "cci_oversold": -100.0, "cci_overbought": 100.0,
            "atr_sl_multiplier": 1.5,
            "min_rr_ratio": 2.0
        },
        "timeframe_overrides": {
            "5m": { "confluence_proximity_percent": 0.2, "atr_sl_multiplier": 1.2 },
            "1d": { "confluence_proximity_percent": 0.5, "min_rr_ratio": 2.5 }
        },
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {
            "min_required_score": 1,
            "adx": {"weight": 1, "min_strength": 25}
        }
    }

    def _get_signal_config(self) -> Dict[str, Any]:
        """ ✅ New: Loads the hierarchical config based on the current timeframe. """
        base_configs = self.config.get("default_params", {})
        tf_overrides = self.config.get("timeframe_overrides", {}).get(self.primary_timeframe, {})
        return {**base_configs, **tf_overrides}

    def _find_best_confluence_zone(self, direction: str, cfg: Dict, pivots_data: Dict, structure_data: Dict) -> Optional[Dict]:
        # This helper remains largely the same
        current_price = self.price_data.get('close')
        if not current_price: return None
        pivot_levels = {lvl['level']: lvl['price'] for lvl in pivots_data.get('levels', [])}
        key_levels = structure_data.get('key_levels', {})
        target_pivot_names = [p for p in cfg['pivot_levels_to_check'] if (p.startswith('S') if direction == "BUY" else p.startswith('R'))]
        target_structures = key_levels.get('supports' if direction == "BUY" else 'resistances', [])
        confluence_zones = []
        for pivot_name in target_pivot_names:
            pivot_price = pivot_levels.get(pivot_name)
            if not pivot_price: continue
            for struct_zone in target_structures:
                struct_price = struct_zone.get('price')
                if struct_price and abs(pivot_price - struct_price) / struct_price * 100 < cfg['confluence_proximity_percent']:
                    zone_price = (pivot_price + struct_price) / 2.0
                    confluence_zones.append({ "price": zone_price, "pivot_name": pivot_name, "structure_zone": struct_zone, "distance_to_price": abs(zone_price - current_price) })
        return min(confluence_zones, key=lambda x: x['distance_to_price']) if confluence_zones else None

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self._get_signal_config()
        if not self.price_data: return None
        
        indicators = {name: self.get_indicator(name) for name in ['pivots', 'structure', 'stochastic', 'cci', 'atr', 'patterns']}
        if not all(indicators.values()): return None

        # --- Zone Identification & Price Test ---
        buy_zone = self._find_best_confluence_zone("BUY", cfg, indicators['pivots'], indicators['structure'])
        sell_zone = self._find_best_confluence_zone("SELL", cfg, indicators['pivots'], indicators['structure'])
        price_low, price_high = self.price_data.get('low'), self.price_data.get('high')
        
        signal_direction, zone_info = None, None
        if buy_zone and price_low and price_low <= buy_zone['price']: signal_direction, zone_info = "BUY", buy_zone
        elif sell_zone and price_high and price_high >= sell_zone['price']: signal_direction, zone_info = "SELL", sell_zone
        else: return None
        
        confirmations = {"confluence_zone": f"Pivot {zone_info['pivot_name']} & Structure (Str: {zone_info['structure_zone']['strength']})"}

        # --- Confirmation Funnel ---
        stoch_k = indicators['stochastic'].get('values', {}).get('k')
        cci_val = indicators['cci'].get('values', {}).get('value')
        if stoch_k is None or cci_val is None: return None
        osc_confirmed = False
        if signal_direction == "BUY" and stoch_k < cfg['stoch_oversold'] and cci_val < cfg['cci_oversold']: osc_confirmed = True
        elif signal_direction == "SELL" and stoch_k > cfg['stoch_overbought'] and cci_val > cfg['cci_overbought']: osc_confirmed = True
        if not osc_confirmed: return None
        confirmations['oscillator_filter'] = f"Passed (Stoch & CCI agree)"

        if not self._get_candlestick_confirmation(signal_direction, min_reliability='Strong'): return None
        confirmations['candlestick_filter'] = "Passed (Strong Pattern)"
        
        if cfg['htf_confirmation_enabled']:
            opposite_direction = "SELL" if signal_direction == "BUY" else "BUY"
            if self._get_trend_confirmation(opposite_direction): return None
            confirmations['htf_filter'] = "Passed (No strong opposing trend)"

        # --- Risk Management & Final Checks ---
        entry_price = self.price_data.get('close')
        if not entry_price: return None
        
        atr_value = indicators['atr'].get('values', {}).get('atr', entry_price * 0.01)
        structure_level = zone_info['structure_zone']['price']
        
        stop_loss = structure_level - (atr_value * cfg['atr_sl_multiplier']) if signal_direction == "BUY" else structure_level + (atr_value * cfg['atr_sl_multiplier'])
            
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        
        if not risk_params or risk_params.get("risk_reward_ratio", 0) < cfg['min_rr_ratio']: return None
        
        # ✅ MIRACLE UPGRADE: Multi-Target Profit System
        pivots_data = indicators['pivots']
        pivot_p_level = next((lvl['price'] for lvl in pivots_data.get('levels', []) if lvl['level'] == 'P'), None)
        if pivot_p_level and risk_params.get('targets'):
            # Set tactical TP1 to the Central Pivot
            risk_params['targets'][0] = pivot_p_level
            # Recalculate R/R based on this more conservative first target
            risk_amount = abs(entry_price - stop_loss)
            if risk_amount > 1e-9:
                risk_params['risk_reward_ratio'] = round(abs(pivot_p_level - entry_price) / risk_amount, 2)
            confirmations['target_adjustment'] = "TP1 set to Central Pivot"
            # Re-check RR after adjustment
            if risk_params.get("risk_reward_ratio", 0) < cfg['min_rr_ratio']: return None

        confirmations['rr_check'] = f"Passed (R/R to TP1: {risk_params.get('risk_reward_ratio')})"
        logger.info(f"✨✨ [{self.strategy_name}] PIVOT SNIPER SIGNAL CONFIRMED! ✨✨")

        return { "direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations }

