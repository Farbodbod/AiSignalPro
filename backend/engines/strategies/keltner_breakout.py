# backend/engines/strategies/keltner_breakout.py (v8.0 - The Hedge-Fund Grade Edition)

import logging
from typing import Dict, Any, Optional, List, Tuple, ClassVar
import pandas as pd
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class KeltnerMomentumBreakout(BaseStrategy):
    """
    KeltnerMomentumBreakout - (v8.0 - The Hedge-Fund Grade Edition)
    -------------------------------------------------------------------------
    This version is hardened to a hedge-fund-grade level based on an exhaustive
    peer review. It incorporates bulletproof, multi-layered data validation,
    hardened logic for all edge cases (NaNs, NoneTypes, invalid configs), and
    a robust internal cooldown, making it the definitive, production-ready
    version of this strategy.
    """
    strategy_name: str = "KeltnerMomentumBreakout"

    default_config: ClassVar[Dict[str, Any]] = {
        "market_regime_filter_enabled": True, "required_regime": "TRENDING", "regime_adx_threshold": 22.0,
        "outlier_candle_shield_enabled": True, "outlier_atr_multiplier": 3.5,
        "exhaustion_shield_enabled": True, "rsi_exhaustion_lookback": 200, "rsi_buy_percentile": 90, "rsi_sell_percentile": 10,
        "min_momentum_score": {"low_tf": 5, "high_tf": 7},
        "cooldown_bars": 5,
        "weights": { "volume_catalyst": 4, "momentum_thrust": 3, "volatility_release": 3 },
        "cci_threshold": 100.0, "min_rr_ratio": 2.0
    }
    
    # --- Helper methods ---
    def _calculate_momentum_score(self, direction: str, whales_data: Dict, cci_data: Dict, bollinger_data: Dict) -> Tuple[int, List[str]]:
        weights, score, confirmations = self.config.get('weights', {}), 0, []
        whales_analysis = (whales_data.get('analysis') or {})
        if whales_analysis.get('is_whale_activity'):
            whale_pressure = str(whales_analysis.get('pressure', '')).lower()
            if (direction == "BUY" and 'buy' in whale_pressure) or (direction == "SELL" and 'sell' in whale_pressure):
                score += weights.get('volume_catalyst', 4); confirmations.append(f"Volume Catalyst (Score: {whales_analysis.get('whale_score', 0)})")
        
        cci_value = (cci_data.get('values') or {}).get('cci', 0.0)
        cci_threshold = self.config.get('cci_threshold', 100.0)
        if (direction == "BUY" and cci_value > cci_threshold) or (direction == "SELL" and cci_value < -cci_threshold):
            score += weights.get('momentum_thrust', 3); confirmations.append(f"CCI Thrust ({cci_value:.2f})")

        if (bollinger_data.get('analysis') or {}).get('is_squeeze_release', False):
            score += weights.get('volatility_release', 3); confirmations.append("Volatility Release")
            
        return score, confirmations

    def _is_trend_exhausted_dynamic(self, direction: str) -> bool:
        cfg = self.config
        lookback = cfg.get('rsi_exhaustion_lookback', 200)
        rsi_data = self.get_indicator('rsi')
        if not rsi_data or not rsi_data.get('values') or self.df is None: return False
        
        rsi_col = next((col for col in self.df.columns if col.startswith('rsi_')), None)
        if not rsi_col or rsi_col not in self.df.columns: return False
        
        rsi_series = self.df[rsi_col].dropna()
        if len(rsi_series) < lookback: return False

        window = rsi_series.tail(lookback)
        # ✅ HARDENED: Sanitize percentile inputs from config.
        high_pct = float(cfg.get('rsi_buy_percentile', 90)); low_pct = float(cfg.get('rsi_sell_percentile', 10))
        high_percentile = min(max(high_pct, 0.0), 100.0) / 100.0
        low_percentile = min(max(low_pct, 0.0), 100.0) / 100.0
        
        high_threshold, low_threshold = window.quantile(high_percentile), window.quantile(low_percentile)
        current_rsi = rsi_series.iloc[-1]
        
        is_exhausted = (direction == "BUY" and current_rsi >= high_threshold) or (direction == "SELL" and current_rsi <= low_threshold)
        if is_exhausted: self._log_criteria("Adaptive Exhaustion Shield", False, f"RSI {current_rsi:.2f} hit dynamic threshold (L:{low_threshold:.2f}/H:{high_threshold:.2f})")
        return is_exhausted

    def _validate_indicators_schema(self, indicators: Dict[str, Dict], schema: Dict[str, List[str]]) -> List[str]:
        missing = []
        for name, needs in schema.items():
            data = indicators.get(name)
            if data is None: missing.append(name); continue
            # ✅ HARDENED: Check for presence of key AND validity of value.
            is_valid = True
            for key in needs:
                val = data.get(key)
                if val is None or ((isinstance(val, dict) or isinstance(val, list)) and not val):
                    is_valid = False; break
            if not is_valid: missing.append(name)
        return missing

    def _get_min_score_for_tf(self) -> int:
        cfg = self.config
        min_cfg = cfg.get('min_momentum_score', {"low_tf": 5, "high_tf": 7})
        tf = getattr(self, "primary_timeframe", "15m")
        return int(min_cfg.get('low_tf', 5)) if tf in ('1m','3m','5m','15m') else int(min_cfg.get('high_tf', 7))

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        if self.df is None or len(self.df) == 0: self._log_final_decision("HOLD", "DataFrame empty or missing."); return None
        
        # ✅ HARDENED: Robust cooldown logic.
        current_bar = len(self.df) - 1
        self.last_signal_bar = getattr(self, "last_signal_bar", -9999) # In-memory fallback
        cooldown_bars = cfg.get('cooldown_bars', 5)
        bars_since_last_signal = current_bar - self.last_signal_bar
        if bars_since_last_signal < cooldown_bars:
            self._log_final_decision("HOLD", f"In cooldown for {cooldown_bars - bars_since_last_signal} more bars."); return None

        if not self.price_data: self._log_final_decision("HOLD", "No price data available."); return None
        
        schema = { 'keltner_channel': ['values','analysis'], 'adx': ['values'], 'cci': ['values'], 'atr': ['values'], 'rsi': ['values'], 'bollinger': ['analysis'], 'whales': ['analysis'] }
        indicators = {name: self.get_indicator(name) for name in schema.keys()}
        missing = self._validate_indicators_schema(indicators, schema)
        if missing: self._log_final_decision("HOLD", f"Indicators missing/invalid schema: {', '.join(missing)}"); return None
        self._log_criteria("Data Availability", True, "All required indicators are valid.")

        if cfg.get('outlier_candle_shield_enabled') and self._is_outlier_candle(atr_multiplier=cfg.get('outlier_atr_multiplier', 3.5)):
            self._log_final_decision("HOLD", "Outlier candle detected."); return None
        
        market_regime, adx_val = self._get_market_regime(adx_threshold=cfg.get('regime_adx_threshold', 22.0))
        if cfg.get('market_regime_filter_enabled') and market_regime != cfg.get('required_regime', 'TRENDING'):
            self._log_final_decision("HOLD", f"Market regime is '{market_regime}'."); return None
        self._log_criteria("Market Regime Filter", True, f"Market is '{market_regime}' (ADX={adx_val:.2f})")

        # ✅ HARDENED: Safer access to nested data.
        keltner_channel = indicators.get('keltner_channel', {})
        keltner_analysis = keltner_channel.get('analysis') or {}
        keltner_pos = str(keltner_analysis.get('position','') or '').lower()
        signal_direction = "BUY" if "breakout above" in keltner_pos else "SELL" if "breakdown below" in keltner_pos else None
        if not signal_direction: self._log_final_decision("HOLD", "No primary Keltner breakout trigger."); return None
        self._log_criteria("Primary Trigger (Keltner Breakout)", True, f"Position: {keltner_pos.title()}")
        
        if cfg.get('exhaustion_shield_enabled') and self._is_trend_exhausted_dynamic(signal_direction):
            self._log_final_decision("HOLD", "Adaptive Trend Exhaustion Shield activated."); return None

        min_score = self._get_min_score_for_tf()
        momentum_score, score_details = self._calculate_momentum_score(signal_direction, indicators['whales'], indicators['cci'], indicators['bollinger'])
        if momentum_score < min_score:
            self._log_final_decision("HOLD", f"Momentum score {momentum_score} < min {min_score}."); return None
        self._log_criteria("Momentum Score Check", True, f"Score={momentum_score} vs min={min_score}")
        confirmations = {"power_score": momentum_score, "score_details": ", ".join(score_details or [])}

        entry_price = self.price_data.get('close')
        stop_loss = (indicators['keltner_channel'].get('values') or {}).get('middle_band')
        if not all(v is not None and pd.notna(v) for v in [entry_price, stop_loss]):
             self._log_final_decision("HOLD", "Risk data missing or invalid (entry/stop)."); return None
            
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        # ✅ HARDENED: Robust check for risk_params and R/R value.
        if not isinstance(risk_params, dict):
            self._log_final_decision("HOLD", "Risk manager returned invalid structure."); return None
        
        min_rr = float(cfg.get('min_rr_ratio', 2.0))
        rr_val = risk_params.get('risk_reward_ratio')
        
        if not risk_params.get('targets') or (rr_val is None or rr_val < min_rr):
            rr_display = f"{rr_val:.2f}" if rr_val is not None else "N/A"
            self._log_final_decision("HOLD", f"Risk/Reward check failed. (R/R: {rr_display})"); return None
        
        confirmations['rr_check'] = f"Passed (R/R: {risk_params.get('risk_reward_ratio')})"
        
        self.last_signal_bar = current_bar
        self._log_final_decision(signal_direction, "All criteria met. Keltner Grandmaster signal confirmed.")
        return { "direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations }
