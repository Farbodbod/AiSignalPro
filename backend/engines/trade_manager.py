# engines/trade_manager.py (نسخه نهایی و هماهنگ با معماری)

import logging
from typing import Dict, Any, List, Optional
from core.models import Trade, Signal # فرض بر این است که مدل کاربر جنگو در Signal و Trade استفاده می‌شود
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()

class TradeManager:
    ## --- اصلاح شد: تابع حالا کاربر را به عنوان ورودی می‌پذیرد --- ##
    def start_trade_from_signal(self, signal_obj: Dict[str, Any], user: User) -> Optional[Trade]:
        """یک سیگنال دریافت کرده و بر اساس آن یک معامله جدید در دیتابیس ایجاد می‌کند."""
        
        signal_type = signal_obj.get("signal_type")
        if not signal_type or signal_type.upper() == "HOLD":
            logger.info(f"Signal is '{signal_type}', no trade will be opened.")
            return None

        # ## --- اصلاح شد: استراتژی از خود آبجکت سیگنال خوانده می‌شود، نه اینکه محاسبه شود --- ##
        entry_price = signal_obj.get("current_price")
        stop_loss = signal_obj.get("stop_loss")
        targets = signal_obj.get("targets")

        if not all([entry_price, stop_loss, targets]):
            logger.error("Cannot open trade due to missing strategy data (SL/TP) in the signal object.")
            return None
        
        try:
            # ابتدا یک آبجکت سیگنال برای ثبت در تاریخچه می‌سازیم
            new_signal_instance = Signal.objects.create(
                user=user,
                symbol=signal_obj.get("symbol"),
                timestamp=signal_obj.get("issued_at"),
                timeframe=signal_obj.get("timeframe"),
                signal_type=signal_type,
                price_at_signal=entry_price,
                details=signal_obj.get("raw_analysis_details", {})
            )

            # سپس معامله را با ارجاع به آن سیگنال ایجاد می‌کنیم
            new_trade = Trade.objects.create(
                user=user,
                signal=new_signal_instance,
                symbol=signal_obj.get("symbol"),
                status='OPEN',
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=targets[0] if targets else None, # اولین تارگت به عنوان TP اصلی
                notes=f"Trade opened based on signal ID: {new_signal_instance.id}"
            )
            logger.info(f"Successfully started new trade: {new_trade.id}")
            return new_trade
            
        except Exception as e:
            logger.error(f"Failed to create trade/signal in database: {e}", exc_info=True)
            return None

    def get_open_trades(self) -> List[Dict[str, Any]]:
        """تمام معاملات باز را از دیتابیس برمی‌گرداند."""
        open_trades = Trade.objects.filter(status='OPEN').order_by('-opened_at')
        
        results = []
        for trade in open_trades:
            results.append({
                "id": str(trade.id),
                "symbol": trade.symbol,
                "entry_price": float(trade.entry_price),
                "opened_at": trade.opened_at.isoformat(),
                "status": trade.status,
                "take_profit": float(trade.take_profit) if trade.take_profit else None,
                "stop_loss": float(trade.stop_loss) if trade.stop_loss else None,
            })
        return results
