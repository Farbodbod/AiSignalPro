# backend/engines/strategies/range_hunter.py (v2.0 - The Grandmaster Edition)

import logging
from typing import Dict, Any, Optional, List, Tuple, ClassVar
import pandas as pd

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class RangeHunterPro(BaseStrategy):
    """
    RangeHunterPro - (v2.0 - The Grandmaster Edition)
    -------------------------------------------------------------------------
    This major evolution transforms the strategy into a grandmaster of risk and
    opportunity management. It introduces a multi-target R/R validation system
    and a Max Stop Loss shield, ensuring it only takes trades with the highest
    strategic value and safest risk profiles. The logic is now at a world-class,
    institutional-grade level.
    """
    strategy_name: str = "RangeHunterPro"

    default_config: ClassVar[Dict[str, Any]] = {
        # --- Market Regime Filters ---
        "regime_filter_enabled": True,
        "max_adx_for_range": 20.0,
        "bbw_squeeze_enabled": True,
        "bbw_quantile": 0.25,

        # --- Entry Trigger ---
        "rsi_confirmation_enabled": True,
        "rsi_oversold_entry": 35.0,
        "rsi_overbought_entry": 65.0,
        
        # --- Risk Management ---
        "sl_atr_multiplier": 1.2,
        "min_rr_ratio": 1.5,
        "max_sl_pct": 3.0, # New in v2.0: Max allowed stop loss percentage
    }

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        if not self.price_data: return None

        # --- 1. Data Availability ---
        required_names = ['bollinger', 'adx', 'rsi', 'atr']
        indicators = {name: self.get_indicator(name) for name in required_names}
        if any(data is None or not data.get('values') for data in indicators.values()):
            self._log_criteria("Data Availability", False, "One or more required indicators are missing/invalid.")
            return None
        self._log_criteria("Data Availability", True, "All hunter indicators are present.")

        # --- 2. Market Regime Identification ---
        if cfg.get('regime_filter_enabled'):
            market_regime, adx_val = self._get_market_regime(adx_threshold=cfg.get('max_adx_for_range', 20.0))
            if market_regime != "RANGING":
                self._log_final_decision("HOLD", f"Market is not ranging (ADX={adx_val:.2f}).")
                return None
            self._log_criteria("ADX Ranging Filter", True, f"ADX is {adx_val:.2f} (Needs < {cfg.get('max_adx_for_range', 20.0)})")

            if cfg.get('bbw_squeeze_enabled'):
                is_in_squeeze = (indicators['bollinger'].get('analysis') or {}).get('is_in_squeeze', False)
                if not is_in_squeeze:
                    self._log_final_decision("HOLD", "Market volatility is too high (not in squeeze).")
                    return None
                self._log_criteria("Bollinger Squeeze Filter", True, "Market is in a low-volatility squeeze.")
        
        # --- 3. Identify Entry Zone ---
        bollinger_values = indicators['bollinger']['values']
        upper_band, lower_band = bollinger_values.get('upper_band'), bollinger_values.get('lower_band')
        if upper_band is None or lower_band is None: self._log_final_decision("HOLD", "Bollinger Bands not available."); return None

        signal_direction = None
        if self.price_data.get('low') <= lower_band: signal_direction = "BUY"
        elif self.price_data.get('high') >= upper_band: signal_direction = "SELL"
        
        if not signal_direction: self._log_final_decision("HOLD", "Price is not at an extreme of the range."); return None
        self._log_criteria("Price at Band", True, f"Price touched {'LOWER' if signal_direction == 'BUY' else 'UPPER'} band.")

        # --- 4. Confirm the Reversal (RSI Trigger) ---
        if cfg.get('rsi_confirmation_enabled'):
            rsi_key = next((k for k in self.df.columns if k.startswith('rsi_')), None)
            if not rsi_key or len(self.df) < 2:
                self._log_final_decision("HOLD", "RSI series not available for confirmation."); return None
            
            rsi_series = self.df[rsi_key]
            rsi_value, prev_rsi_value = rsi_series.iloc[-1], rsi_series.iloc[-2]

            buy_thresh, sell_thresh = cfg.get('rsi_oversold_entry', 35.0), cfg.get('rsi_overbought_entry', 65.0)
            buy_triggered = signal_direction == "BUY" and prev_rsi_value < buy_thresh and rsi_value >= buy_thresh
            sell_triggered = signal_direction == "SELL" and prev_rsi_value > sell_thresh and rsi_value <= sell_thresh
            trigger_ok = buy_triggered or sell_triggered
            
            if not trigger_ok:
                reason = f"RSI did not confirm reversal. Dir: {signal_direction}, RSI: {rsi_value:.2f}, Prev: {prev_rsi_value:.2f}"
                self._log_final_decision("HOLD", reason)
                return None
            self._log_criteria("RSI Reversal Trigger", True, f"RSI crossed threshold (Current: {rsi_value:.2f}, Prev: {prev_rsi_value:.2f})")

        # --- 5. Engineer the Trade ---
        entry_price = self.price_data.get('close')
        atr_value = (indicators['atr']['values'] or {}).get('atr')
        if entry_price is None or atr_value is None or atr_value <= 0:
            self._log_final_decision("HOLD", f"Invalid data for risk engineering (Entry: {entry_price}, ATR: {atr_value})."); return None

        # --- 5a. Max Stop Loss Shield ---
        stop_loss = lower_band - (atr_value * cfg.get('sl_atr_multiplier', 1.2)) if signal_direction == "BUY" else upper_band + (atr_value * cfg.get('sl_atr_multiplier', 1.2))
        max_sl_pct = cfg.get('max_sl_pct', 3.0)
        sl_pct = (abs(entry_price - stop_loss) / entry_price) * 100
        if sl_pct > max_sl_pct:
            self._log_criteria("Max Stop Loss Shield", False, f"Stop loss ({sl_pct:.2f}%) exceeds max allowed ({max_sl_pct}%)")
            self._log_final_decision("HOLD", "Calculated stop loss is too risky.")
            return None
        self._log_criteria("Max Stop Loss Shield", True, f"Stop loss ({sl_pct:.2f}%) is within safe limits.")
        
        # --- 5b. Multi-Target R/R Intelligence ---
        tp1 = bollinger_values.get('middle_band')
        tp2 = upper_band if signal_direction == "BUY" else lower_band
        if tp1 is None or tp2 is None:
             self._log_final_decision("HOLD", "Could not determine valid TP levels from Bollinger Bands."); return None
        
        potential_targets = [tp1, tp2]
        risk_amount = abs(entry_price - stop_loss)
        
        valid_targets = []
        rr_values = []
        if risk_amount > 1e-9:
            for target in potential_targets:
                reward_amount = abs(target - entry_price)
                rr = round(reward_amount / risk_amount, 2)
                rr_values.append(rr)
                if rr >= cfg.get('min_rr_ratio', 1.5):
                    valid_targets.append(target)
        
        if not valid_targets:
            self._log_criteria("Multi-Target R/R Check", False, f"No potential target meets min R/R. R/Rs: {rr_values}")
            self._log_final_decision("HOLD", "Trade failed R/R check for all potential targets.")
            return None
        self._log_criteria("Multi-Target R/R Check", True, f"{len(valid_targets)} target(s) met min R/R. R/Rs: {rr_values}")

        # --- 6. Final Decision ---
        final_rr = rr_values[0] # Use R/R to first target for reporting
        risk_params = {"stop_loss": stop_loss, "targets": valid_targets, "risk_reward_ratio": final_rr}
        confirmations = {"market_regime": "RANGING", "entry_trigger": "RSI Reversal from Band", "rr_check": f"Passed (R/R to TP1: {final_rr:.2f})"}
        self._log_final_decision(signal_direction, "All criteria met. Range Hunter signal confirmed.")

        return { "direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations }

