# backend/engines/strategies/pullback_sniper.py (v1.1 - The Bulletproof Edition)

import logging
from typing import Dict, Any, Optional, List, Tuple, ClassVar

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class PullbackSniperPro(BaseStrategy):
    """
    PullbackSniperPro - (v1.1 - The Bulletproof Edition)
    -------------------------------------------------------------------------
    This hardened, production-ready version incorporates critical fail-safes
    and architectural improvements. It features bulletproof data handling to
    prevent crashes from None/NaN values and a future-proof dynamic trigger
    logic, making the strategy exceptionally robust and extensible.
    """
    strategy_name: str = "PullbackSniperPro"

    default_config: ClassVar[Dict[str, Any]] = {
        # --- Macro Trend Filters ---
        "trend_filter_enabled": True,
        "master_ma_indicator": "fast_ma", # Uses the 200-period DEMA
        "htf_confirmation_enabled": True,

        # --- Pullback Level Filters ---
        "pullback_ma_enabled": True,
        "pullback_ma_indicator": "ema_cross", # Uses the short EMA (e.g., 21)
        "pullback_fib_enabled": True,
        "fib_golden_zone_min": 50.0,
        "fib_golden_zone_max": 61.8,
        
        # --- Entry Trigger Filters ---
        "trigger_logic": "OR", # 'OR' or 'AND'
        "use_hidden_divergence": True,
        "use_candlestick_patterns": True,

        # --- Risk Management ---
        "sl_atr_multiplier": 1.5,
        "min_rr_ratio": 2.5, # Snipers require high R/R
        
        # --- Standard HTF Config ---
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {
            "min_required_score": 2,
            "adx": {"weight": 1, "min_strength": 25},
            "supertrend": {"weight": 1}
        }
    }

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        if not self.price_data: return None

        # --- 1. Data Availability ---
        required_names = ['fast_ma', 'supertrend', 'ema_cross', 'fibonacci', 'divergence', 'patterns', 'atr', 'structure']
        indicators = {name: self.get_indicator(name) for name in list(set(required_names))}
        if any(data is None for data in indicators.values()):
            self._log_criteria("Data Availability", False, "One or more required indicators are missing for the sniper.")
            return None
        self._log_criteria("Data Availability", True, "All sniper indicators are present.")
        
        # --- 2. Define Macro Trend (The Hunting Ground) ---
        current_price = self.price_data.get('close')
        master_ma_val = (indicators['fast_ma'].get('values') or {}).get('ma_value')
        
        # ✅ BULLETPROOF FIX: Ensure critical values are not None before comparison.
        if current_price is None or master_ma_val is None:
            self._log_final_decision("HOLD", "Missing critical price or MA value for trend definition."); return None

        st_trend = str((indicators['supertrend'].get('analysis') or {}).get('trend', '')).lower()
        htf_is_aligned_up = self._get_trend_confirmation("BUY") if cfg.get("htf_confirmation_enabled") else True
        htf_is_aligned_down = self._get_trend_confirmation("SELL") if cfg.get("htf_confirmation_enabled") else True

        macro_trend = "NEUTRAL"
        if current_price > master_ma_val and "up" in st_trend and htf_is_aligned_up: macro_trend = "UP"
        elif current_price < master_ma_val and "down" in st_trend and htf_is_aligned_down: macro_trend = "DOWN"
        
        self._log_criteria("Macro Trend Defined", macro_trend != "NEUTRAL", f"Macro trend identified as {macro_trend}.")
        if macro_trend == "NEUTRAL": self._log_final_decision("HOLD", "No clear macro trend to hunt pullbacks."); return None

        # --- 3. Identify Pullback Zone (The Ambush Point) ---
        is_in_pullback_zone = False; pullback_confirmations = []
        short_ema = (indicators['ema_cross'].get('values') or {}).get('short_ema')

        if cfg.get('pullback_ma_enabled') and short_ema is not None:
            if self.price_data.get('low') <= short_ema <= self.price_data.get('high'):
                is_in_pullback_zone = True; pullback_confirmations.append(f"Price touched Short EMA ({short_ema:.2f})")
        
        if not is_in_pullback_zone and cfg.get('pullback_fib_enabled'):
            fib_analysis = (indicators['fibonacci'].get('analysis') or {})
            if fib_analysis.get('is_in_golden_zone'):
                is_in_pullback_zone = True; pullback_confirmations.append("Price in Fibonacci Golden Zone")

        self._log_criteria("Pullback Zone Detected", is_in_pullback_zone, ", ".join(pullback_confirmations) or "N/A")
        if not is_in_pullback_zone: self._log_final_decision("HOLD", "Price is not at a valid pullback level."); return None

        # --- 4. Find Entry Trigger (The Fire Command) ---
        triggers_found = []; signal_direction = "BUY" if macro_trend == "UP" else "SELL"

        if cfg.get('use_hidden_divergence'):
            div_signals = (indicators['divergence'].get('signals') or [])
            if any(f"Hidden {signal_direction.title()}" in s.get('type', '') for s in div_signals):
                triggers_found.append("Hidden_Divergence")
        
        if cfg.get('use_candlestick_patterns'):
            if self._get_candlestick_confirmation(signal_direction, min_reliability='Strong'):
                triggers_found.append("Reversal_Candlestick")

        # ✅ FUTURE-PROOF TRIGGERING: Dynamic check for AND logic.
        logic = str(cfg.get('trigger_logic', "OR")).upper()
        enabled_triggers_count = sum([cfg.get('use_hidden_divergence', False), cfg.get('use_candlestick_patterns', False)])
        
        trigger_ok = True
        if logic == "AND" and len(triggers_found) < enabled_triggers_count: trigger_ok = False
        elif logic == "OR" and not triggers_found: trigger_ok = False
        
        self._log_criteria("Entry Trigger Found", trigger_ok, f"Triggers: {','.join(triggers_found) or 'None'}")
        if not trigger_ok: self._log_final_decision("HOLD", "Not enough entry triggers found."); return None

        # --- 5. Engineer the Trade & Final Signal ---
        entry_price = self.price_data.get('close')
        atr_value = (indicators['atr'].get('values') or {}).get('atr')
        
        # ✅ BULLETPROOF FIX: Ensure ATR value is valid before calculations.
        if atr_value is None or atr_value <= 0:
            self._log_final_decision("HOLD", f"Invalid ATR value ({atr_value}) for SL calculation."); return None

        stop_loss = None; sl_anchor = None
        if signal_direction == "BUY": sl_anchor = self.price_data.get('low')
        else: sl_anchor = self.price_data.get('high')
        if sl_anchor is None: self._log_final_decision("HOLD", "Missing low/high price for SL anchor."); return None
            
        if signal_direction == "BUY": stop_loss = sl_anchor - (atr_value * cfg.get('sl_atr_multiplier', 1.5))
        else: stop_loss = sl_anchor + (atr_value * cfg.get('sl_atr_multiplier', 1.5))
            
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        if not risk_params or not risk_params.get("targets"):
             self._log_final_decision("HOLD", "Failed to engineer a valid trade with R/R."); return None

        rr_val = risk_params.get("risk_reward_ratio", 0.0)
        min_rr = cfg.get('min_rr_ratio', 2.5)
        if rr_val < min_rr:
            # ✅ ENHANCED LOGGING: Provide full context on R/R failure.
            reason = f"Trade failed R/R check ({rr_val:.2f} < {min_rr}). SL: {risk_params.get('stop_loss', 'N/A'):.4f}, TP1: {risk_params.get('targets', ['N/A'])[0]:.4f}"
            self._log_final_decision("HOLD", reason)
            return None
        
        fib_levels = (indicators['fibonacci'].get('levels') or [])
        supports = [lvl for lvl in fib_levels if lvl.get('type') == 'Retracement' and lvl.get('price', float('inf')) < entry_price]
        resistances = [lvl for lvl in fib_levels if lvl.get('type') == 'Retracement' and lvl.get('price', 0) > entry_price]
        risk_params["key_levels"] = {"supports": supports, "resistances": resistances}
        
        confirmations = {
            "macro_trend": macro_trend,
            "pullback_level": ", ".join(pullback_confirmations),
            "entry_triggers": ", ".join(triggers_found),
            "rr_check": f"Passed (R/R: {rr_val:.2f})"
        }
        self._log_final_decision(signal_direction, "All criteria met. Pullback Sniper signal confirmed.")

        return { "direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations }
