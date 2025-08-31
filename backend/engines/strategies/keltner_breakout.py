# backend/engines/strategies/keltner_breakout.py (v10.2 - Diagnostic & Contract Fix)

import logging
from typing import Dict, Any, Optional, List, Tuple, ClassVar
import pandas as pd
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class KeltnerMomentumBreakout(BaseStrategy):
    """
    KeltnerMomentumBreakout - (v10.2 - Diagnostic & Contract Fix)
    -------------------------------------------------------------------------
    This version includes two critical fixes:
    1.  **Diagnostic Patch:** The silent exit on indicator failure has been
        replaced with robust logging, ensuring that any issues with indicator
        loading are now explicitly reported instead of causing the strategy
        to disappear from the logs.
    2.  **Data Contract Hotfix:** Corrects the data contract with the Volume
        Indicator (v2.0) by reading 'z_score' from the 'values' dictionary,
        restoring the "Volume Catalyst" scoring component.
    """
    strategy_name: str = "KeltnerMomentumBreakout"

    default_config: ClassVar[Dict[str, Any]] = {
        "market_regime_filter_enabled": True, "required_regime": "TRENDING", "regime_adx_threshold": 21.0,
        "outlier_candle_shield_enabled": True, "outlier_atr_multiplier": 3.5,
        "exhaustion_shield_enabled": True, "rsi_exhaustion_lookback": 200, "rsi_buy_percentile": 90, "rsi_sell_percentile": 10,
        "cooldown_bars": 3,
        "min_momentum_score": {"low_tf": 8, "high_tf": 10},
        "weights": { 
            "momentum_acceleration": 4, "volume_catalyst": 3, "volatility_expansion": 2,
            "adx_strength": 1, "htf_alignment": 2, "candlestick": 1
        },
        "volume_z_score_threshold": 1.75,
        "late_entry_atr_mult": 1.2,
        "max_structural_sl_atr_mult": 2.5,
        "atr_sl_multiplier": 1.5,
        "target_atr_multiples": [1.5, 3.0, 4.5],
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": { 
            "min_required_score": 2, 
            "adx": {"weight": 1, "min_strength": 25}, 
            "supertrend": {"weight": 1} 
        }
    }
    
    def _is_valid_number(self, x: Any) -> bool:
        return x is not None and isinstance(x, (int, float)) and pd.notna(x)

    def _calculate_momentum_score(self, direction: str, indicators: Dict) -> Tuple[int, List[str]]:
        weights, score, confirmations = self.config.get('weights', {}), 0, []
        
        def check(name: str, weight_key: str, condition: bool):
            nonlocal score
            if condition:
                points = weights.get(weight_key, 0)
                score += points
                confirmations.append(name)

        cci_analysis = (indicators.get('cci', {}).get('analysis') or {})
        # ✅ FIX v10.2: Correctly read from 'values' for z_score
        volume_values = (indicators.get('volume', {}).get('values') or {})
        keltner_analysis = (indicators.get('keltner_channel', {}).get('analysis') or {})
        adx_values = (indicators.get('adx', {}).get('values') or {})

        mom_state = cci_analysis.get('momentum_state', '')
        is_accel = (direction == "BUY" and mom_state == 'Accelerating Bullish') or \
                   (direction == "SELL" and mom_state == 'Accelerating Bearish')
        check("Momentum Acceleration", "momentum_acceleration", is_accel)

        z_score_thresh = self.config.get('volume_z_score_threshold', 1.75)
        is_vol_catalyst = (volume_values.get('z_score', 0) or 0) > z_score_thresh
        check("Volume Catalyst", "volume_catalyst", is_vol_catalyst)

        is_vol_expansion = keltner_analysis.get('volatility_state') == 'Expansion'
        check("Volatility Expansion", "volatility_expansion", is_vol_expansion)
        
        adx_strength = adx_values.get('adx', 0.0)
        is_adx_strong = adx_strength >= 25.0
        check("ADX Strength", "adx_strength", is_adx_strong)

        if self.config.get('htf_confirmation_enabled', True):
            check("HTF Aligned", "htf_alignment", self._get_trend_confirmation(direction))

        if self._get_candlestick_confirmation(direction, min_reliability='Medium'):
            check("Candlestick Confirmed", "candlestick", True)
        
        return score, confirmations

    def _is_trend_exhausted_dynamic(self, direction: str) -> bool:
        cfg = self.config; lookback = cfg.get('rsi_exhaustion_lookback', 200)
        rsi_data = self.get_indicator('rsi');
        if not rsi_data or not rsi_data.get('values') or self.df is None: return False
        rsi_col = next((col for col in self.df.columns if col.startswith('rsi_')), None)
        if not rsi_col or rsi_col not in self.df.columns: return False
        rsi_series = self.df[rsi_col].dropna();
        if len(rsi_series) < lookback: return False
        window = rsi_series.tail(lookback)
        high_pct = float(cfg.get('rsi_buy_percentile', 90)); low_pct = float(cfg.get('rsi_sell_percentile', 10))
        high_threshold, low_threshold = window.quantile(high_pct/100.0), window.quantile(low_pct/100.0)
        current_rsi = rsi_series.iloc[-1]
        is_exhausted = (direction == "BUY" and current_rsi >= high_threshold) or (direction == "SELL" and current_rsi <= low_threshold)
        if is_exhausted: self._log_criteria("Adaptive Exhaustion Shield", False, f"RSI {current_rsi:.2f} hit dynamic threshold (L:{low_threshold:.2f}/H:{high_threshold:.2f})")
        return is_exhausted

    def _get_min_score_for_tf(self) -> int:
        cfg = self.config; min_cfg = cfg.get('min_momentum_score', {"low_tf": 8, "high_tf": 10})
        tf = getattr(self, "primary_timeframe", "15m")
        return int(min_cfg.get('low_tf', 8)) if tf in ('1m','3m','5m','15m') else int(min_cfg.get('high_tf', 10))

    def _validate_blueprint(self, blueprint: Dict[str, Any]) -> bool:
        required_keys = ["direction", "entry_price", "sl_logic", "tp_logic"]
        for key in required_keys:
            if key not in blueprint:
                logger.error(f"Blueprint validation failed: Missing key '{key}'.")
                return False
        if not isinstance(blueprint.get('sl_logic'), dict) or not isinstance(blueprint.get('tp_logic'), dict):
            logger.error("Blueprint validation failed: sl_logic or tp_logic is not a dictionary.")
            return False
        return True

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        if self.df is None or self.df.empty: return None
        current_bar = len(self.df) - 1
        last_signal_bar = getattr(self, "last_signal_bar", -9999)
        if (current_bar - last_signal_bar) < cfg.get('cooldown_bars', 3): return None
        if not self.price_data: return None

        required = ['keltner_channel', 'cci', 'volume', 'adx', 'atr', 'rsi', 'patterns', 'supertrend']
        indicators = {name: self.get_indicator(name) for name in required}

        # ✅ FIX v10.2: Implement robust logging for missing indicators to prevent silent exits.
        missing_indicators = [name for name, data in indicators.items() if data is None]
        if missing_indicators:
            self._log_final_decision("HOLD", f"Required indicators are missing: {', '.join(missing_indicators)}")
            return None

        keltner_analysis = (indicators['keltner_channel'].get('analysis') or {})
        signal_direction = "BUY" if "breakout above" in str(keltner_analysis.get('position','')) else "SELL" if "breakdown below" in str(keltner_analysis.get('position','')) else None
        if not signal_direction: return None
        self._log_criteria("Primary Trigger", True, f"Position: {keltner_analysis.get('position')}")
        if cfg.get('outlier_candle_shield_enabled') and self._is_outlier_candle(atr_multiplier=cfg.get('outlier_atr_multiplier', 3.5)):
            self._log_final_decision("HOLD", "Outlier candle detected."); return None
        market_regime, adx_val = self._get_market_regime(adx_threshold=cfg.get('regime_adx_threshold', 21.0))
        if cfg.get('market_regime_filter_enabled') and market_regime != cfg.get('required_regime', 'TRENDING'):
            self._log_final_decision("HOLD", f"Market regime is '{market_regime}'."); return None
        self._log_criteria("Market Regime Filter", True, f"Market is '{market_regime}' (ADX={adx_val:.2f})")
        entry_price = self.price_data.get('close')
        atr_val = (indicators['atr'].get('values') or {}).get('atr')
        breakout_level = keltner_analysis.get('breakout_level')
        if self._is_valid_number(entry_price) and self._is_valid_number(atr_val) and self._is_valid_number(breakout_level):
            if abs(entry_price - breakout_level) > (cfg.get('late_entry_atr_mult', 1.2) * atr_val):
                self._log_final_decision("HOLD", f"Late-Entry Guard: Price too far from breakout."); return None
        self._log_criteria("Late-Entry Guard", True, "Entry is close to breakout level.")
        if cfg.get('exhaustion_shield_enabled') and self._is_trend_exhausted_dynamic(signal_direction):
            self._log_final_decision("HOLD", "Adaptive Trend Exhaustion Shield activated."); return None
        min_score = self._get_min_score_for_tf()
        momentum_score, score_details = self._calculate_momentum_score(signal_direction, indicators)
        if momentum_score < min_score:
            self._log_final_decision("HOLD", f"Momentum score {momentum_score} < min {min_score}."); return None
        self._log_criteria("Momentum Score Check", True, f"Score={momentum_score} vs min={min_score} ({', '.join(score_details)})")
        keltner_values = (indicators['keltner_channel'].get('values') or {})
        structural_sl = keltner_values.get('middle_band')
        sl_logic = {}
        if self._is_valid_number(structural_sl) and self._is_valid_number(atr_val):
            sl_dist = abs(entry_price - structural_sl)
            max_sl_dist = cfg.get('max_structural_sl_atr_mult', 2.5) * atr_val
            if sl_dist > max_sl_dist:
                sl_logic = {'type': 'atr_based', 'atr_multiplier': cfg.get('atr_sl_multiplier', 1.5)}
            else:
                sl_logic = {'type': 'structural', 'level_name': 'middle_band', 'indicator': 'keltner_channel'}
        else:
            self._log_final_decision("HOLD", "Could not calculate valid SL logic."); return None
        tp_logic = {'type': 'atr_multiple', 'multiples': cfg.get('target_atr_multiples', [1.5, 3.0, 4.5])}
        self.last_signal_bar = current_bar
        blueprint = { 
            "direction": signal_direction, "entry_price": entry_price, "trade_mode": "Early Strike Breakout",
            "sl_logic": sl_logic, "tp_logic": tp_logic,
            "confirmations": {"power_score": momentum_score, "details": ", ".join(score_details)}
        }
        if self._validate_blueprint(blueprint):
            self._log_final_decision(signal_direction, "Keltner Early Strike blueprint generated.")
            return blueprint
        self._log_final_decision("HOLD", "Generated blueprint failed validation.")
        return None
