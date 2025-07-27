import logging
from typing import Dict, Any, List
from core.models import Trade # <<-- مدل دیتابیس خود را وارد می‌کنیم

logger = logging.getLogger(__name__)

class TradeManager:

    def start_trade_from_signal(self, signal_obj: Dict[str, Any]) -> Trade:
        """یک سیگنال دریافت کرده و یک معامله جدید در دیتابیس ایجاد می‌کند."""
        
        signal_type = signal_obj.get("signal_type")
        if signal_type not in ["BUY", "SELL"]:
            logger.info(f"Signal is '{signal_type}', no trade will be opened.")
            return None

        direction = 'long' if signal_type == "BUY" else 'short'

        # استخراج هوشمندانه حد ضرر و تارگت از دیتای خام تحلیل
        # این بخش را بعداً می‌توان با risk_manager بسیار پیشرفته‌تر کرد
        stop_loss = None
        targets = []
        try:
            # تلاش برای پیدا کردن اولین تارگت و استاپ لاس معقول از دیتای خام
            first_tf_details = next(iter(signal_obj.get("raw_analysis_details", {}).get("details", {}).values()))
            indicators = first_tf_details.get("indicators", {})
            price = signal_obj.get("current_price", 0)

            if direction == 'long':
                stop_loss = indicators.get("boll_lower", price * 0.98) # حد ضرر: باند بولینگر پایینی یا ۲٪ پایین‌تر
                targets.append(indicators.get("boll_upper", price * 1.04)) # حد سود: باند بولینگر بالایی یا ۴٪ بالاتر
            else: # short
                stop_loss = indicators.get("boll_upper", price * 1.02) # حد ضرر: باند بولینگر بالایی یا ۲٪ بالاتر
                targets.append(indicators.get("boll_lower", price * 0.96)) # حد سود: باند بولینگر پایینی یا ۴٪ پایین‌تر
        except (StopIteration, AttributeError):
             logger.warning("Could not determine SL/TP from indicators, using default percentages.")
             price = signal_obj.get("current_price", 0)
             if direction == 'long':
                 stop_loss = price * 0.98
                 targets = [price * 1.04]
             else:
                 stop_loss = price * 1.02
                 targets = [price * 0.96]


        try:
            new_trade = Trade.objects.create(
                symbol=signal_obj.get("symbol"),
                timeframe=signal_obj.get("timeframe"),
                direction=direction,
                status='OPEN',
                entry_price=signal_obj.get("current_price"),
                stop_loss=stop_loss,
                targets=targets,
                raw_signal_data=signal_obj
            )
            logger.info(f"Successfully started new trade: {new_trade.id}")
            return new_trade
        except Exception as e:
            logger.error(f"Failed to create trade in database: {e}")
            return None

    def get_open_trades(self) -> List[Dict[str, Any]]:
        """تمام معاملات باز را از دیتابیس برمی‌گرداند."""
        open_trades = Trade.objects.filter(status='OPEN').order_by('-entry_time')
        
        results = []
        for trade in open_trades:
            results.append({
                "id": str(trade.id),
                "symbol": trade.symbol,
                "direction": trade.direction,
                "entry_price": trade.entry_price,
                "entry_time": trade.entry_time.isoformat(),
                "status": trade.status,
                "targets": trade.targets,
                "stop_loss": trade.stop_loss,
            })
        return results
