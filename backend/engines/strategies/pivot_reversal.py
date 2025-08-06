import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

from .base_strategy import BaseStrategy

class PivotReversalStrategy(BaseStrategy):
    """
    ✨ UPGRADE v3.0 - PivotConfluenceSniper ✨
    یک استراتژی بازگشتی بسیار دقیق که به دنبال تلاقی (Confluence) بین پیوت‌های
    کلاسیک و سطوح ساختاری بازار می‌گردد و با تایید دوگانه اسیلاتورها و
    الگوهای کندلی، سیگنال ورود صادر می‌کند.
    """
    def __init__(self, analysis_summary: Dict[str, Any], config: Dict[str, Any] = None, htf_analysis: Optional[Dict[str, Any]] = None):
        super().__init__(analysis_summary, config, htf_analysis)
        self.strategy_name = "PivotConfluenceSniper"

    def _get_signal_config(self) -> Dict[str, Any]:
        """
        پارامترهای قابل تنظیم استراتژی را از فایل کانفیگ بارگیری می‌کند.
        """
        return {
            "pivot_levels_to_check": self.config.get("pivot_levels_to_check", ['R2', 'R1', 'S1', 'S2']),
            "confluence_proximity_percent": self.config.get("confluence_proximity_percent", 0.003), # 0.3%
            "stoch_oversold": self.config.get("stoch_oversold", 20),
            "stoch_overbought": self.config.get("stoch_overbought", 80),
            "cci_oversold": self.config.get("cci_oversold", -100),
            "cci_overbought": self.config.get("cci_overbought", 100),
            "atr_sl_multiplier": self.config.get("atr_sl_multiplier", 1.2)
        }
        
    def _find_confluence_zones(self, pivots_data, structure_data, direction):
        """متد کمکی برای پیدا کردن نواحی تلاقی."""
        cfg = self._get_signal_config()
        pivot_levels = pivots_data.get('levels', {})
        structure_levels = structure_data.get('key_levels', {})
        target_pivots = [p for p in cfg['pivot_levels_to_check'] if p.startswith('S' if direction == "BUY" else 'R')]
        target_structures = structure_levels.get('supports' if direction == "BUY" else 'resistances', [])
        
        confluence_zones = []
        for pivot_name in target_pivots:
            pivot_price = pivot_levels.get(pivot_name)
            if not pivot_price: continue
            for struct_price in target_structures:
                if abs(pivot_price - struct_price) / struct_price < cfg['confluence_proximity_percent']:
                    confluence_zones.append({"price": (pivot_price + struct_price) / 2, "pivot_name": pivot_name, "structure_price": struct_price})
        return confluence_zones

    def check_signal(self) -> Optional[Dict[str, Any]]:
        # 1. دریافت داده‌ها
        cfg = self._get_signal_config()
        pivots_data = self.analysis.get('pivots'); structure_data = self.analysis.get('structure'); stoch_data = self.analysis.get('stochastic'); cci_data = self.analysis.get('cci'); price_data = self.analysis.get('price_data'); atr_data = self.analysis.get('atr')
        if not all([pivots_data, structure_data, stoch_data, cci_data, price_data, atr_data]): return None

        # 2. پیدا کردن نواحی تلاقی برای هر دو جهت
        buy_zones = self._find_confluence_zones(pivots_data, structure_data, "BUY")
        sell_zones = self._find_confluence_zones(pivots_data, structure_data, "SELL")
        
        potential_direction, zone_info = (None, None)
        
        # 3. بررسی تست نواحی و تایید اسیلاتورها
        if buy_zones and price_data['low'] <= buy_zones[0]['price']:
            if stoch_data['percent_k'] < cfg['stoch_oversold'] and cci_data['value'] < cfg['cci_oversold']:
                potential_direction, zone_info = "BUY", buy_zones[0]
        
        if not potential_direction and sell_zones and price_data['high'] >= sell_zones[0]['price']:
            if stoch_data['percent_k'] > cfg['stoch_overbought'] and cci_data['value'] > cfg['cci_overbought']:
                potential_direction, zone_info = "SELL", sell_zones[0]

        if not potential_direction: return None
        
        # 4. تایید نهایی با کندل استیک
        confirming_pattern = self._get_candlestick_confirmation(potential_direction)
        if not confirming_pattern: return None
        
        logger.info(f"✨ [{self.strategy_name}] Confluence Reversal signal for {potential_direction} fully confirmed!")

        # 5. محاسبه مدیریت ریسک
        entry_price = price_data['close']; atr_value = atr_data.get('value'); stop_loss = None
        structure_level = zone_info['structure_price']
        stop_loss = structure_level - (atr_value * cfg['atr_sl_multiplier']) if potential_direction == "BUY" else structure_level + (atr_value * cfg['atr_sl_multiplier'])
            
        risk_params = self._calculate_smart_risk_management(entry_price, potential_direction, stop_loss)
        if pivots_data.get('levels', {}).get('P'): risk_params['targets'][0] = pivots_data['levels']['P']

        # 6. آماده‌سازی خروجی نهایی
        confirmations = {
            "confluence_at": round(zone_info['price'], 5),
            "trigger_level": f"Pivot {zone_info['pivot_name']} + Structure {zone_info['structure_price']}",
            "oscillator_confirmation": f"Stoch({round(stoch_data['percent_k'],1)}) & CCI({round(cci_data['value'],1)})",
            "candlestick_pattern": confirming_pattern
        }
        
        return {"strategy_name": self.strategy_name, "direction": potential_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations}
