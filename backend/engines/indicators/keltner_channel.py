# backend/engines/indicators/keltner_channel.py (v8.2 - Breakout Logic Hotfix)
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

from .base import BaseIndicator
from .utils import get_indicator_config_key

logger = logging.getLogger(__name__)

class KeltnerChannelIndicator(BaseIndicator):
    """
    Keltner Channel - (v8.2 - Breakout Logic Hotfix)
    -----------------------------------------------------------------------------
    This version includes a critical hotfix to the breakout detection logic.
    Instead of incorrectly comparing the 'close' price to the bands, it now
    uses the standard and correct method of comparing the candle's 'high'
    against the upper band and the 'low' against the lower band. This ensures
    that true breakouts and breakdowns are accurately detected and reported.
    """
    # dependencies: list = ['atr'] # This attribute is obsolete in the new architecture
    
    default_config: Dict[str, Any] = {
        'ema_period': 20,
        'atr_multiplier': 2.0,
        'volatility_period': 200,
        'squeeze_percentile': 20,
        'expansion_percentile': 80,
        'dependencies': {
            'atr': {'period': 10}
        }
    }

    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], **kwargs):
        super().__init__(df, params=params, **kwargs)
        self.ema_period = int(self.params.get('ema_period', self.default_config['ema_period']))
        self.atr_multiplier = float(self.params.get('atr_multiplier', self.default_config['atr_multiplier']))
        self.volatility_period = int(self.params.get('volatility_period', self.default_config['volatility_period']))
        self.squeeze_percentile = int(self.params.get('squeeze_percentile', self.default_config['squeeze_percentile']))
        self.expansion_percentile = int(self.params.get('expansion_percentile', self.default_config['expansion_percentile']))
        self.timeframe = self.params.get('timeframe')
        
        atr_params = self.params.get("dependencies", {}).get("atr", self.default_config['dependencies']['atr'])
        atr_period = int(atr_params.get('period', 10))
        suffix = f'_{self.ema_period}_{self.atr_multiplier}_{atr_period}'
        if self.timeframe: suffix += f'_{self.timeframe}'
        
        self.upper_col = f'KC_U{suffix}'
        self.lower_col = f'KC_L{suffix}'
        self.middle_col = f'KC_M{suffix}'
        self.bandwidth_col = f'KC_BW{suffix}'
        self.bw_percentile_col = f'KC_BW_PCT{suffix}'

    def calculate(self) -> 'KeltnerChannelIndicator':
        my_deps_config = self.params.get("dependencies", self.default_config['dependencies'])
        atr_order_params = my_deps_config.get('atr')
        
        atr_unique_key = get_indicator_config_key('atr', atr_order_params)
        atr_instance = self.dependencies.get(atr_unique_key)
        
        if not isinstance(atr_instance, BaseIndicator) or not hasattr(atr_instance, 'atr_col'):
            # Assuming BaseIndicator might not have a `name` attribute, using self.__class__.__name__
            logger.warning(f"[{self.__class__.__name__}] on {self.timeframe}: missing or invalid ATR instance ('{atr_unique_key}').")
            return self
        
        atr_col_name = atr_instance.atr_col
        if atr_col_name not in atr_instance.df.columns:
             logger.warning(f"[{self.__class__.__name__}] on {self.timeframe}: could not find ATR column '{atr_col_name}'.")
             return self
        
        df_for_calc = self.df.join(atr_instance.df[[atr_col_name]], how='left')
        atr_period = int(atr_instance.params.get('period', 10))

        if len(df_for_calc) < max(self.ema_period, atr_period, self.volatility_period):
            logger.warning(f"Not enough data for Keltner Channel on {self.timeframe or 'base'}.")
            return self

        typical_price = (df_for_calc['high'] + df_for_calc['low'] + df_for_calc['close']) / 3
        middle_band = typical_price.ewm(span=self.ema_period, adjust=False).mean()
        atr_value = df_for_calc[atr_col_name].dropna() * self.atr_multiplier
        
        self.df[self.upper_col] = middle_band + atr_value
        self.df[self.lower_col] = middle_band - atr_value
        self.df[self.middle_col] = middle_band
        
        bandwidth = ((self.df[self.upper_col] - self.df[self.lower_col]) / self.df[self.middle_col].replace(0, np.nan)) * 100
        self.df[self.bandwidth_col] = bandwidth
        
        self.df[self.bw_percentile_col] = bandwidth.rolling(window=self.volatility_period, min_periods=int(self.volatility_period/2)).rank(pct=True) * 100
        
        return self

    def analyze(self) -> Dict[str, Any]:
        required_cols = [self.upper_col, self.lower_col, self.middle_col, self.bandwidth_col, self.bw_percentile_col, 'high', 'low']
        empty_analysis = {"values": {}, "analysis": {}}
        if not all(col in self.df.columns for col in required_cols):
            return {"status": "Calculation Incomplete", **empty_analysis}

        valid_df = self.df.dropna(subset=required_cols)
        if len(valid_df) < 2:
            return {"status": "Insufficient Data for Analysis", **empty_analysis}

        last = valid_df.iloc[-1]
        previous = valid_df.iloc[-2]
        
        # ✅ HOTFIX v8.2: Use high and low for breakout detection
        high, low = last['high'], last['low']
        upper, middle, lower = last[self.upper_col], last[self.middle_col], last[self.lower_col]
        
        position = "Inside Channel"
        breakout_level = None
        if high > upper:
            position = "Breakout Above"
            breakout_level = previous[self.upper_col]
        elif low < lower:
            position = "Breakdown Below"
            breakout_level = previous[self.lower_col]

        bw_percentile = last[self.bw_percentile_col]
        volatility_state = "Normal"
        if bw_percentile <= self.squeeze_percentile:
            volatility_state = "Squeeze"
        elif bw_percentile >= self.expansion_percentile:
            volatility_state = "Expansion"

        values_content = {
            "upper_band": round(upper, 5),
            "middle_band": round(middle, 5),
            "lower_band": round(lower, 5),
            "bandwidth_percent": round(last[self.bandwidth_col], 2),
            "width_percentile": round(bw_percentile, 2)
        }
        
        analysis_content = {
            "position": position,
            "breakout_level": round(breakout_level, 5) if breakout_level is not None else None,
            "volatility_state": volatility_state
        }
        
        return {
            "status": "OK", "timeframe": self.timeframe or 'Base',
            "values": values_content,
            "analysis": analysis_content
        }
