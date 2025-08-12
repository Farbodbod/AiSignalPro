import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class EmaCrossoverStrategy(BaseStrategy):
    """
    EmaCrossoverStrategy - (v3.0 - Miracle Confirmation Engine)
    -------------------------------------------------------------------
    This world-class version transforms the classic EMA Crossover into a multi-layered
    trend analysis framework. It operates on three core pillars:
    1.  Master Trend Filter: Validates crossovers against a long-term moving average.
    2.  Crossover Strength Engine: Confirms signals with both momentum (MACD) and volume (Whales).
    3.  Dynamic Risk Framework: Uses an adaptive ATR multiplier for stop loss based on volatility.
    """
    strategy_name: str = "EmaCrossoverStrategy"

    # ✅ MIRACLE UPGRADE: Default configuration for the new engines
    default_config = {
        "min_adx_strength": 23.0,
        "candlestick_confirmation_enabled": True,
        # Pillar 1: Master Trend Filter
        "master_trend_filter": {
            "enabled": True,
            "ma_indicator": "fast_ma", # Uses fast_ma indicator
            "ma_period": 200 # Assumes fast_ma is configured to this period
        },
        # Pillar 2: Crossover Strength Engine
        "strength_engine": {
            "macd_confirmation_enabled": True,
            "volume_confirmation_enabled": True
        },
        # Pillar 3: Dynamic Risk Framework
        "volatility_regimes": {
            "low_atr_pct_threshold": 1.5,
            "low_vol_sl_multiplier": 2.0,
            "high_vol_sl_multiplier": 3.0
        },
        # HTF Engine (from BaseStrategy v4.0)
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {
            "min_required_score": 2,
            "adx": {"weight": 1, "min_strength": 25},
            "supertrend": {"weight": 1}
        }
    }

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        
        # --- 1. Anti-Fragile Data Check ---
        if not self.price_data: return None
        
        # Fetch all potential indicators
        ema_cross_data = self.get_indicator('ema_cross')
        adx_data = self.get_indicator('adx')
        atr_data = self.get_indicator('atr')
        master_ma_data = self.get_indicator(cfg['master_trend_filter'].get('ma_indicator', 'fast_ma'))
        macd_data = self.get_indicator('macd')
        whales_data = self.get_indicator('whales')

        # Core dependencies
        if not all([ema_cross_data, adx_data, atr_data]):
            return None

        # --- 2. Get Primary Signal ---
        primary_signal = ema_cross_data.get('analysis', {}).get('signal')
        if primary_signal not in ["Buy", "Sell"]: return None
        
        signal_direction = primary_signal.upper()
        confirmations = {"entry_trigger": f"EMA Cross"}

        # --- 3. MIRACLE CONFIRMATION FUNNEL ---
        # ✅ Pillar 1: Master Trend Filter
        trend_cfg = cfg.get('master_trend_filter', {})
        if trend_cfg.get('enabled') and master_ma_data:
            ma_value = master_ma_data.get('values', {}).get('ma_value')
            if not ma_value: return None
            if (signal_direction == "BUY" and self.price_data.get('close', 0) < ma_value) or \
               (signal_direction == "SELL" and self.price_data.get('close', 0) > ma_value):
                return None
            confirmations['master_trend_filter'] = "Passed (Aligned with long-term MA)"

        # ✅ Pillar 2: Crossover Strength Engine
        strength_cfg = cfg.get('strength_engine', {})
        if strength_cfg.get('macd_confirmation_enabled'):
            if not macd_data: return None
            histo = macd_data.get('values', {}).get('histogram', 0)
            if (signal_direction == "BUY" and histo < 0) or (signal_direction == "SELL" and histo > 0):
                return None
            confirmations['macd_filter'] = "Passed (Momentum Confirmed)"

        if strength_cfg.get('volume_confirmation_enabled'):
            if not self._get_volume_confirmation(): return None
            confirmations['volume_filter'] = "Passed (Volume Confirmed)"

        # ADX Filter
        if adx_data.get('values', {}).get('adx', 0) < cfg['min_adx_strength']: return None
        confirmations['adx_filter'] = f"Passed (ADX: {adx_data['values']['adx']:.2f})"
        
        # HTF Confirmation (from BaseStrategy v4.0)
        if cfg['htf_confirmation_enabled']:
            if not self._get_trend_confirmation(signal_direction): return None
            confirmations['htf_filter'] = "Passed (HTF Aligned)"

        # Candlestick Confirmation
        if cfg['candlestick_confirmation_enabled']:
            if not self._get_candlestick_confirmation(signal_direction): return None
            confirmations['candlestick_filter'] = "Passed"

        logger.info(f"✨✨ [{self.strategy_name}] Signal for {signal_direction} confirmed! ✨✨")

        # --- ✅ Pillar 3: Dynamic Risk Management ---
        entry_price = self.price_data.get('close')
        long_ema_val = ema_cross_data.get('values', {}).get('long_ema')
        if not all([entry_price, long_ema_val]): return None
            
        # Determine volatility regime to select the correct SL multiplier
        vol_cfg = cfg.get('volatility_regimes', {})
        atr_pct = atr_data.get('values', {}).get('atr_percent', 2.0)
        is_low_vol = atr_pct < vol_cfg.get('low_atr_pct_threshold', 1.5)
        atr_sl_multiplier = vol_cfg.get('low_vol_sl_multiplier', 2.0) if is_low_vol else vol_cfg.get('high_vol_sl_multiplier', 3.0)
        
        atr_value = atr_data.get('values', {}).get('atr', 0)
        stop_loss = long_ema_val - (atr_value * atr_sl_multiplier) if signal_direction == "BUY" else long_ema_val + (atr_value * atr_sl_multiplier)

        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        if not risk_params or not risk_params.get("targets"): return None

        # --- 5. Package and Return the Final Signal ---
        return {
            "direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations
        }
