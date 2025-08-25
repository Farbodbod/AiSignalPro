# backend/engines/strategies/keltner_breakout.py (v9.2 - The Unified & Bulletproof Engine)

import logging
from typing import Dict, Any, Optional, List, Tuple, ClassVar
import pandas as pd
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class KeltnerMomentumBreakout(BaseStrategy):
    """
    KeltnerMomentumBreakout - (v9.2 - The Unified & Bulletproof Engine)
    -------------------------------------------------------------------------
    This is the definitive, hedge-fund-grade version. It unifies the strategic
    flexibility of a fully configurable weighting engine (v9.0) with the
    bulletproof engineering and hardening patches of v9.1, creating the ultimate
    version of this strategy.
    """
    strategy_name: str = "KeltnerMomentumBreakout"

    default_config: ClassVar[Dict[str, Any]] = {
        "market_regime_filter_enabled": True, "required_regime": "TRENDING", "regime_adx_threshold": 22.0,
        "outlier_candle_shield_enabled": True, "outlier_atr_multiplier": 3.5,
        "exhaustion_shield_enabled": True, "rsi_exhaustion_lookback": 200, "rsi_buy_percentile": 90, "rsi_sell_percentile": 10,
        "min_momentum_score": 7,
        "cooldown_bars": 5,
        "weights": { 
            "volume_catalyst": 4, "momentum_thrust": 3, "volatility_release": 3, # Fast Confirmations
            "adx_strength": 0, "htf_alignment": 0, "candlestick": 0 # Slow Confirmations (off by default)
        },
        "adx_threshold": 25.0, "cci_threshold": 100.0, "min_rr_ratio": 2.0
    }
    
    # --- Helper methods ---
    def _is_valid_number(self, x: Any) -> bool:
        return x is not None and isinstance(x, (int, float)) and pd.notna(x)

    def _calculate_momentum_score(self, direction: str, indicators: Dict) -> Tuple[int, List[str]]:
        weights, score, confirmations = self.config.get('weights', {}), 0, []
        
        # Fast Confirmations
        whales_analysis = (indicators.get('whales', {}).get('analysis') or {})
        if whales_analysis.get('is_whale_activity'):
            whale_pressure = str(whales_analysis.get('pressure', '')).lower()
            if (direction == "BUY" and 'buy' in whale_pressure) or (direction == "SELL" and 'sell' in whale_pressure):
                score += weights.get('volume_catalyst', 0); confirmations.append(f"Volume Catalyst")

        cci_values = (indicators.get('cci', {}).get('values') or {})
        cci_value = cci_values.get('cci', 0.0)
        if (direction == "BUY" and cci_value > self.config.get('cci_threshold', 100.0)) or \
           (direction == "SELL" and cci_value < -self.config.get('cci_threshold', 100.0)):
            score += weights.get('momentum_thrust', 0); confirmations.append(f"CCI Thrust")
        
        bollinger_analysis = (indicators.get('bollinger', {}).get('analysis') or {})
        if bollinger_analysis.get('is_squeeze_release', False):
            score += weights.get('volatility_release', 0); confirmations.append("Volatility Release")

        # Slow/Lagging Confirmations
        adx_values = (indicators.get('adx', {}).get('values') or {})
        adx_strength = adx_values.get('adx', 0.0)
        if adx_strength >= self.config.get('adx_threshold', 25.0):
            score += weights.get('adx_strength', 0); confirmations.append(f"ADX Strength")

        if self._get_trend_confirmation(direction):
            score += weights.get('htf_alignment', 0); confirmations.append("HTF Aligned")

        if self._get_candlestick_confirmation(direction, min_reliability='Medium'):
            score += weights.get('candlestick', 0); confirmations.append("Candlestick Confirmed")
            
        return score, confirmations

    def _is_trend_exhausted_dynamic(self, direction: str) -> bool:
        # ... [Unchanged and correct] ...
        cfg = self.config; lookback = cfg.get('rsi_exhaustion_lookback', 200)
        rsi_data = self.get_indicator('rsi');
        if not rsi_data or not rsi_data.get('values') or self.df is None: return False
        rsi_col = next((col for col in self.df.columns if col.startswith('rsi_')), None)
        if not rsi_col or rsi_col not in self.df.columns: return False
        rsi_series = self.df[rsi_col].dropna();
        if len(rsi_series) < lookback: return False
        window = rsi_series.tail(lookback)
        high_pct = float(cfg.get('rsi_buy_percentile', 90)); low_pct = float(cfg.get('rsi_sell_percentile', 10))
        high_percentile = min(max(high_pct, 0.0), 100.0) / 100.0; low_percentile = min(max(low_pct, 0.0), 100.0) / 100.0
        high_threshold, low_threshold = window.quantile(high_percentile), window.quantile(low_percentile)
        current_rsi = rsi_series.iloc[-1]
        is_exhausted = (direction == "BUY" and current_rsi >= high_threshold) or (direction == "SELL" and current_rsi <= low_threshold)
        if is_exhausted: self._log_criteria("Adaptive Exhaustion Shield", False, f"RSI {current_rsi:.2f} hit dynamic threshold (L:{low_threshold:.2f}/H:{high_threshold:.2f})")
        return is_exhausted

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        if self.df is None or self.df.empty: self._log_final_decision("HOLD", "DataFrame empty."); return None
        current_bar = len(self.df) - 1
        last_signal_bar = getattr(self, "last_signal_bar", -9999)
        cooldown_bars = cfg.get('cooldown_bars', 5)
        if (current_bar - last_signal_bar) < cooldown_bars:
            self._log_final_decision("HOLD", f"In cooldown for {cooldown_bars - (current_bar - last_signal_bar)} more bars."); return None

        if not self.price_data: self._log_final_decision("HOLD", "No price data available."); return None
        
        required_names = ['keltner_channel', 'adx', 'cci', 'atr', 'rsi', 'bollinger', 'whales', 'patterns', 'supertrend']
        indicators = {name: self.get_indicator(name) for name in required_names}
        if any(data is None for data in indicators.values()):
            self._log_final_decision("HOLD", f"Indicators missing: {[k for k,v in indicators.items() if v is None]}"); return None
        self._log_criteria("Data Availability", True, "All required indicators are valid.")

        if cfg.get('outlier_candle_shield_enabled') and self._is_outlier_candle(atr_multiplier=cfg.get('outlier_atr_multiplier', 3.5)):
            self._log_final_decision("HOLD", "Outlier candle detected."); return None
        
        market_regime, adx_val = self._get_market_regime(adx_threshold=cfg.get('regime_adx_threshold', 22.0))
        adx_text = f"{adx_val:.2f}" if self._is_valid_number(adx_val) else "N/A"
        if cfg.get('market_regime_filter_enabled') and market_regime != cfg.get('required_regime', 'TRENDING'):
            self._log_final_decision("HOLD", f"Market regime is '{market_regime}'."); return None
        self._log_criteria("Market Regime Filter", True, f"Market is '{market_regime}' (ADX={adx_text})")

        keltner_analysis = (indicators.get('keltner_channel', {}).get('analysis') or {})
        keltner_pos = str(keltner_analysis.get('position','') or '').lower()
        signal_direction = "BUY" if "breakout above" in keltner_pos else "SELL" if "breakdown below" in keltner_pos else None
        if not signal_direction: self._log_final_decision("HOLD", "No primary Keltner breakout trigger."); return None
        self._log_criteria("Primary Trigger", True, f"Position: {keltner_pos.title()}")
        
        if cfg.get('exhaustion_shield_enabled') and self._is_trend_exhausted_dynamic(signal_direction):
            self._log_final_decision("HOLD", "Adaptive Trend Exhaustion Shield activated."); return None

        momentum_score, score_details = self._calculate_momentum_score(signal_direction, indicators)
        min_score = cfg.get('min_momentum_score', 7)
        if momentum_score < min_score:
            self._log_final_decision("HOLD", f"Momentum score {momentum_score} < min {min_score}."); return None
        self._log_criteria("Momentum Score Check", True, f"Score={momentum_score} vs min={min_score}")
        
        entry_price = self.price_data.get('close')
        stop_loss = (indicators.get('keltner_channel', {}).get('values') or {}).get('middle_band')
        if not self._is_valid_number(entry_price) or not self._is_valid_number(stop_loss):
             self._log_final_decision("HOLD", "Risk data missing or invalid (entry/stop)."); return None
            
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        if not isinstance(risk_params, dict):
            self._log_final_decision("HOLD", "Risk manager returned invalid structure."); return None
        
        min_rr = float(cfg.get('min_rr_ratio', 2.0))
        rr_val = risk_params.get('risk_reward_ratio')
        
        if not risk_params.get('targets') or rr_val is None or rr_val < min_rr:
            rr_display = f"{rr_val:.2f}" if rr_val is not None else "N/A"
            self._log_final_decision("HOLD", f"Risk/Reward check failed. (R/R: {rr_display})"); return None
        
        confirmations = {"power_score": momentum_score, "score_details": (", ".join(score_details) if score_details else "None"), "rr_check": f"Passed (R/R: {risk_params.get('risk_reward_ratio')})"}
        
        self.last_signal_bar = current_bar
        self._log_final_decision(signal_direction, "All criteria met. Keltner Unified Engine signal confirmed.")
        return { "direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations }
