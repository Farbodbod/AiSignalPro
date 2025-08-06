import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class IchimokuProStrategy(BaseStrategy):
    """
    ✨ UPGRADE v3.0 - IchimokuHybridPro ✨
    یک استراتژی ایچیموکوی هیبریدی که سیستم امتیازدهی داخلی خود را با
    فیلترهای خارجی قدرت روند (ADX) و مدیریت ریسک ساختاری (ZigZag) ترکیب می‌کند.
    """
    
    def __init__(self, analysis_summary: Dict[str, Any], config: Dict[str, Any] = None, htf_analysis: Optional[Dict[str, Any]] = None):
        super().__init__(analysis_summary, config, htf_analysis)
        self.strategy_name = "IchimokuHybridPro"
    
    def _get_signal_config(self) -> Dict[str, Any]:
        """
        پارامترهای قابل تنظیم استراتژی را از فایل کانفیگ بارگیری می‌کند.
        """
        return {
            "min_score_to_signal": self.config.get("min_score_to_signal", 5),
            "min_adx_strength": self.config.get("min_adx_strength", 23), # آستانه ADX
            "zigzag_deviation": self.config.get("zigzag_deviation", 5.0), # برای پیدا کردن پیوت‌ها
            "atr_sl_multiplier": self.config.get("atr_sl_multiplier", 1.0)
        }

    def check_signal(self) -> Optional[Dict[str, Any]]:
        # 1. دریافت داده‌ها و کانفیگ
        cfg = self._get_signal_config()
        ichimoku_data = self.analysis.get('ichimoku'); price_data = self.analysis.get('price_data'); adx_data = self.analysis.get('adx'); zigzag_data = self.analysis.get(f'zigzag_{cfg["zigzag_deviation"]}'); atr_data = self.analysis.get('atr')
        
        if not all([ichimoku_data, price_data, adx_data, zigzag_data, atr_data]):
            return None
            
        # 2. محاسبه امتیاز ایچیموکو (منطق اصلی بدون تغییر)
        buy_score, sell_score, confirmations = 0, 0, []
        price = price_data['close']
        # ... (کپی کردن کامل منطق امتیازدهی از نسخه قبلی شما)
        price_pos = ichimoku_data.get('price_position'); tk_cross = ichimoku_data.get('signal', 'Neutral'); chikou_confirm = ichimoku_data.get('chikou_confirmation'); kijun = ichimoku_data.get('kijun_sen'); senkou_a = ichimoku_data.get('senkou_span_a'); senkou_b = ichimoku_data.get('senkou_span_b')
        if price_pos == "Above Kumo": buy_score += 3; confirmations.append("Above Kumo")
        elif price_pos == "Below Kumo": sell_score += 3; confirmations.append("Below Kumo")
        if "Bullish" in tk_cross: buy_score += 2; confirmations.append(tk_cross)
        elif "Bearish" in tk_cross: sell_score += 2; confirmations.append(tk_cross)
        if chikou_confirm == "Bullish Confirmation": buy_score += 1; confirmations.append(chikou_confirm)
        elif chikou_confirm == "Bearish Confirmation": sell_score += 1; confirmations.append(chikou_confirm)
        if price > kijun: buy_score += 1; confirmations.append("Price above Kijun")
        elif price < kijun: sell_score += 1; confirmations.append("Price below Kijun")
        if senkou_a > senkou_b: buy_score += 1; confirmations.append("Future Kumo is Bullish")
        elif senkou_a < senkou_b: sell_score += 1; confirmations.append("Future Kumo is Bearish")

        signal_direction = None
        if buy_score >= cfg['min_score_to_signal']: signal_direction = "BUY"
        elif sell_score >= cfg['min_score_to_signal']: signal_direction = "SELL"
        
        if not signal_direction: return None
        
        # 3. فیلتر شماره ۱: قدرت روند (ADX)
        if adx_data['adx'] < cfg['min_adx_strength']:
            logger.info(f"[{self.strategy_name}] Ichimoku signal ignored. ADX ({adx_data['adx']:.2f}) indicates a non-trending market.")
            return None
        
        logger.info(f"✨ [{self.strategy_name}] Ichimoku signal with score {buy_score if signal_direction == 'BUY' else sell_score} confirmed by ADX!")

        # 4. محاسبه مدیریت ریسک با حد ضرر ساختاری ZigZag
        last_pivot = zigzag_data.get('values', {})
        if not last_pivot or last_pivot.get('last_pivot_type') not in ['peak', 'trough']:
            logger.warning(f"[{self.strategy_name}] Could not find a valid ZigZag pivot for Stop Loss.")
            return None # اگر پیوتی برای تعیین حد ضرر نباشد، سیگنال را لغو کن
        
        # آیا آخرین پیوت با جهت سیگنال ما همخوانی دارد؟ (برای مثال، برای سیگنال خرید، آخرین پیوت باید یک کف باشد)
        if (signal_direction == "BUY" and last_pivot['last_pivot_type'] != 'trough') or \
           (signal_direction == "SELL" and last_pivot['last_pivot_type'] != 'peak'):
           logger.info(f"[{self.strategy_name}] Signal ignored. Last ZigZag pivot does not match signal direction.")
           return None

        pivot_price = last_pivot['last_pivot_price']; atr_value = atr_data.get('value');
        stop_loss = pivot_price - (atr_value * cfg['atr_sl_multiplier']) if signal_direction == "BUY" else pivot_price + (atr_value * cfg['atr_sl_multiplier'])
        
        risk_params = self._calculate_smart_risk_management(price, signal_direction, stop_loss)
        
        # 5. آماده‌سازی خروجی نهایی
        final_confirmations = {
            "ichimoku_score": buy_score if signal_direction == "BUY" else sell_score,
            "ichimoku_details": ", ".join(confirmations),
            "trend_filter": f"ADX at {round(adx_data['adx'], 2)}",
            "risk_management": f"SL based on ZigZag {last_pivot['last_pivot_type']} at {pivot_price}"
        }

        return {"strategy_name": self.strategy_name, "direction": signal_direction, "entry_price": price, **risk_params, "confirmations": final_confirmations}
