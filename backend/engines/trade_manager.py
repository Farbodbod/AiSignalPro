import logging
from typing import Dict, Any, List
from core.models import Trade

logger = logging.getLogger(__name__)

class TradeManager:

    def start_trade_from_signal(self, signal_obj: Dict[str, Any]) -> Trade:
        """یک سیگنال دریافت کرده و یک معامله جدید در دیتابیس ایجاد می‌کند."""
        
        signal_type = signal_obj.get("signal_type")
        if signal_type not in ["BUY", "SELL"]:
            logger.info(f"Signal is '{signal_type}', no trade will be opened.")
            return None

        direction = 'long' if signal_type == "BUY" else 'short'

        stop_loss = None
        targets = []
        try:
            first_tf_details = next(iter(signal_obj.get("raw_analysis_details", {}).get("details", {}).values()))
            indicators = first_tf_details.get("indicators", {})
            price = signal_obj.get("current_price", 0)

            if direction == 'long':
                stop_loss = indicators.get("boll_lower", price * 0.98)
                targets.append(indicators.get("boll_upper", price * 1.04))
            else: # short
                stop_loss = indicators.get("boll_upper", price * 1.02)
                targets.append(indicators.get("boll_lower", price * 0.96))
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
        # --- اصلاحیه: entry_time به opened_at تغییر کرد ---
        open_trades = Trade.objects.filter(status='OPEN').order_by('-opened_at')
        
        results = []
        for trade in open_trades:
            results.append({
                "id": str(trade.id),
                "symbol": trade.symbol,
                "direction": trade.direction,
                "entry_price": float(trade.entry_price),
                "entry_time": trade.opened_at.isoformat(), # <<-- اصلاح شد
                "status": trade.status,
                "targets": trade.targets,
                "stop_loss": float(trade.stop_loss) if trade.stop_loss else None,
            })
        return results
