# backend/engines/strategies/ichimacdpro.py (v3.4 - The Verbose Striker)

import logging
from typing import Dict, Any, Optional, Tuple, ClassVar, List

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class IchiMACDPro(BaseStrategy):
    """
    IchiMACDPro - (v3.4 - The Verbose Striker)
    -----------------------------------------------------------------------------------------
    This version applies a critical logging discipline fix. It removes a "silent exit"
    path by adding a final decision log when the primary Ichimoku trigger is not found.
    This ensures that every execution path concludes with a clear, logged reason,
    eliminating any ambiguity in the strategy's decision-making process.
    """
    strategy_name: str = "IchiMACDPro"

    default_config: ClassVar[Dict[str, Any]] = {
        "market_regime_filter": {
            "enabled": True,
            "min_adx_percentile": 60.0
        },
        "min_rr_ratio": 2.0,
        "exhaustion_shield": {
            "enabled": True,
            "rsi_lookback": 120,
            "rsi_buy_percentile": 88,
            "rsi_sell_percentile": 12
        },
        "indicator_configs": {
            "ichimoku": { "name": "ichimoku" },
            "macd":     { "name": "macd" },
            "rsi":      { "name": "rsi" },
            "adx":      { "name": "adx" } 
        }
    }

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        
        required_names = ['ichimoku', 'macd', 'rsi', 'adx', 'structure', 'pivots', 'atr']
        
        indicators = {name: self.get_indicator(name) for name in required_names}
        if any(data is None for data in indicators.values()):
            missing = [name for name, data in indicators.items() if data is None]
            self._log_final_decision("HOLD", f"Indicators missing: {', '.join(missing)}"); return None

        # --- STAGE 1: MARKET REGIME FILTER ---
        regime_cfg = cfg.get('market_regime_filter', {})
        if regime_cfg.get('enabled', True):
            adx_percentile = self._safe_get(indicators['adx'], ['analysis', 'adx_percentile'], 0.0)
            min_percentile = regime_cfg.get('min_adx_percentile', 60.0)
            if adx_percentile < min_percentile:
                self._log_final_decision("HOLD", f"Market is not trending. ADX Percentile {adx_percentile:.2f}% < {min_percentile}%.")
                return None
        self._log_criteria("Market Regime Filter", True, "Market is in a trending state.")

        # --- STAGE 2: ENTRY TRIGGER ---
        ichi_analysis = self._safe_get(indicators['ichimoku'], ['analysis'], {})
        tsa_cross = ichi_analysis.get('tsa_cross')
        
        signal_direction = None
        if tsa_cross == "Bullish Crossover": signal_direction = "BUY"
        elif tsa_cross == "Bearish Crossover": signal_direction = "SELL"

        if not signal_direction:
            # ✅ SURGICAL FIX v3.3: Added a log before the silent exit.
            self._log_final_decision("HOLD", "Market is trending, but no IchiMACD trigger was found.")
            return None
        self._log_criteria("Entry Trigger (Ichimoku)", True, f"Found potential '{tsa_cross}' signal.")
        
        # --- STAGE 3: THE ASYMMETRICAL DEFENSIVE SHIELD ---
        shield_cfg = cfg.get('exhaustion_shield', {})
        if shield_cfg.get('enabled', True):
            rsi_data = indicators.get('rsi')
            rsi_col = next((col for col in self.df.columns if col.startswith('RSI_')), None)
            if rsi_data and rsi_col and rsi_col in self.df.columns:
                rsi_series = self.df[rsi_col].dropna()
                rsi_lookback = shield_cfg.get('rsi_lookback', 120)
                if len(rsi_series) >= rsi_lookback:
                    window = rsi_series.tail(rsi_lookback)
                    current_rsi = rsi_series.iloc[-1]
                    if signal_direction == "BUY":
                        buy_percentile = shield_cfg.get('rsi_buy_percentile', 88)
                        high_threshold = window.quantile(buy_percentile / 100.0)
                        if current_rsi >= high_threshold:
                            self._log_final_decision("HOLD", f"Vetoed by Shield: BUY signal while RSI is Overbought ({current_rsi:.2f} >= {high_threshold:.2f})")
                            return None
                    elif signal_direction == "SELL":
                        sell_percentile = shield_cfg.get('rsi_sell_percentile', 12)
                        low_threshold = window.quantile(sell_percentile / 100.0)
                        if current_rsi <= low_threshold:
                           self._log_final_decision("HOLD", f"Vetoed by Shield: SELL signal while RSI is Oversold ({current_rsi:.2f} <= {low_threshold:.2f})")
                           return None
        self._log_criteria("Defensive Shield", True, "Signal passed asymmetrical exhaustion check.")

        # --- STAGE 4: QUALITATIVE CONFIRMATION (MACD) ---
        macd_context = self._safe_get(indicators['macd'], ['analysis', 'context'], {})
        histogram_state = macd_context.get('histogram_state')
        required_state = "Green" if signal_direction == "BUY" else "Red"
        
        if histogram_state != required_state:
            self._log_final_decision("HOLD", f"MACD confirmation failed. Required '{required_state}', got '{histogram_state}'.")
            return None
        self._log_criteria("Qualitative Confirmation (MACD)", True, f"MACD state '{histogram_state}' confirms momentum.")
        
        # --- STAGE 5: RISK ORCHESTRATION ---
        entry_price = self._safe_get(self.price_data, ['close'])
        self.config['override_min_rr_ratio'] = cfg.get('min_rr_ratio', 2.0)
        risk_params = self._orchestrate_static_risk(direction=signal_direction, entry_price=entry_price)
        self.config.pop('override_min_rr_ratio', None)

        if not risk_params:
            self._log_final_decision("HOLD", "OHRE engine failed to generate a valid risk plan."); return None
            
        confirmations = {
            "entry_trigger": tsa_cross,
            "momentum_confirmation": f"MACD State: {histogram_state} (Strength: {self._safe_get(indicators['macd'], ['analysis', 'strength'])})",
            "risk_engine": self.log_details["risk_trace"][-1].get("source", "OHRE v3.0"),
            "risk_reward": risk_params.get('risk_reward_ratio'),
        }
        self._log_final_decision(signal_direction, "IchiMACD Striker signal confirmed.")
        
        return {"direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations}
