import pandas as pd
import logging
import time
import json
from typing import Dict, Any, List, Type, Optional

from .indicator_analyzer import IndicatorAnalyzer
from .gemini_handler import GeminiHandler
# ✨ ۱. ایمپورت کردن تمام استراتژی‌های جدید و ارتقا یافته از __init__.py پوشه strategies
from .strategies import *

logger = logging.getLogger(__name__)

class MasterOrchestrator:
    """
    ✨ UPGRADE v18.1 - JSON Config Ready ✨
    مغز متفکر و هماهنگ‌کننده اصلی پروژه AiSignalPro.
    این کلاس تمام تحلیلگرها و استراتژی‌ها را بر اساس یک فایل کانفیگ مرکزی
    مدیریت و اجرا می‌کند.
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # لیست کامل و جامع از تمام استراتژی‌های پروژه برای اجرا
        self._strategy_classes: List[Type[BaseStrategy]] = [
            # استراتژی‌های قدیمی که ارتقا دادیم
            TrendRiderStrategy, 
            MeanReversionStrategy, 
            DivergenceSniperStrategy, 
            PivotReversalStrategy, 
            VolumeCatalystStrategy, 
            IchimokuProStrategy,
            # استراتژی‌های جدیدی که ساختیم
            EmaCrossoverStrategy, 
            BreakoutStrategy, 
            ChandelierTrendStrategy,
            VolumeReversalStrategy, 
            VwapReversionStrategy, 
            KeltnerBreakoutStrategy,
            FibStructureStrategy
        ]
        self.gemini_handler = GeminiHandler()
        self.last_gemini_call_time = 0
        self.ENGINE_VERSION = "18.1.0"
        logger.info(f"MasterOrchestrator v{self.ENGINE_VERSION} (JSON Config Ready) initialized.")

    def _find_super_signal(self, signals: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        در میان سیگنال‌های معتبر، به دنبال تلاقی (Confluence) برای یافتن "سوپر سیگنال" می‌گردد.
        """
        min_confluence = self.config.get("general", {}).get("min_confluence_for_super_signal", 3)
        buy_signals = [s for s in signals if s['direction'] == 'BUY']
        sell_signals = [s for s in signals if s['direction'] == 'SELL']
        
        super_direction, contributing_strategies = (None, [])
        if len(buy_signals) >= min_confluence:
            super_direction, contributing_strategies = ("BUY", buy_signals)
        elif len(sell_signals) >= min_confluence:
            super_direction, contributing_strategies = ("SELL", sell_signals)
        
        if not super_direction:
            return None
            
        priority_list = self.config.get("strategy_priority", [])
        contributing_strategies.sort(key=lambda s: priority_list.index(s.get('strategy_name', '')) if s.get('strategy_name', '') in priority_list else 99)
        primary_signal = contributing_strategies[0]
        
        super_signal = {
            "strategy_name": "SuperSignal Confluence",
            "direction": super_direction,
            "entry_price": primary_signal['entry_price'],
            "stop_loss": primary_signal['stop_loss'],
            "targets": primary_signal['targets'],
            "risk_reward_ratio": primary_signal['risk_reward_ratio'],
            "confirmations": {
                "confluence_count": len(contributing_strategies),
                "contributing_strategies": [s['strategy_name'] for s in contributing_strategies]
            }
        }
        logger.info(f"🔥🔥 SUPER SIGNAL FOUND! {super_direction} with {len(contributing_strategies)} confirmations. 🔥🔥")
        return super_signal

    def _get_ai_confirmation(self, signal: Dict[str, Any], symbol: str, timeframe: str) -> Optional[Dict[str, Any]]:
        """
        یک سیگنال را برای تایید نهایی به Gemini AI ارسال می‌کند.
        """
        cooldown = self.config.get("general", {}).get('gemini_cooldown_seconds', 300)
        if (time.time() - self.last_gemini_call_time) < cooldown:
            logger.info("Gemini call skipped due to cooldown.")
            return {"signal": "N/A", "confidence": 0, "explanation_fa": "AI analysis skipped due to cooldown."}

        prompt_context = {
            "symbol": symbol,
            "timeframe": timeframe,
            "signal_details": {k: v for k, v in signal.items() if k != 'confirmations'},
            "system_reasons": signal.get('confirmations')
        }
        prompt = (f"Analyze this trading signal for {symbol} on the {timeframe} timeframe. Based ONLY on the provided data, respond ONLY in JSON with three keys: 'signal' (Your confirmation: 'BUY', 'SELL', or 'HOLD'), 'confidence_percent' (A number from 1 to 100), and 'explanation_fa' (A very concise, one-sentence explanation in Persian).\n\nData: {json.dumps(prompt_context, indent=2)}")
        
        self.last_gemini_call_time = time.time()
        ai_response = self.gemini_handler.query(prompt)

        if ai_response.get('signal') == 'HOLD':
            logger.warning(f"AI VETOED the signal for {symbol}. System signal was {signal['direction']}.")
            return None # بازگرداندن None به معنی وتو شدن سیگنال است

        return ai_response

    def run_full_pipeline(self, df: pd.DataFrame, symbol: str, timeframe: str) -> Optional[Dict[str, Any]]:
        """
        خط لوله کامل تحلیل را اجرا می‌کند: از محاسبه اندیکاتورها تا اجرای استراتژی‌ها و تایید AI.
        """
        # پاس دادن کانفیگ اندیکاتورها به موتور تحلیلگر
        analyzer = IndicatorAnalyzer(df, config=self.config.get('indicators', {}))
        analyzer.calculate_all()
        analysis_summary = analyzer.get_analysis_summary()
        
        valid_signals = []
        strategy_configs = self.config.get('strategies', {})
        for sc in self._strategy_classes:
            strategy_name_key = sc.__name__
            strategy_config = strategy_configs.get(strategy_name_key, {})
            
            if strategy_config.get('enabled', True):
                instance = sc(analysis_summary, strategy_config, htf_analysis=None) # TODO: Pass HTF analysis
                signal = instance.check_signal()
                if signal:
                    # نام استراتژی را از داخل خود نمونه می‌خوانیم تا نام‌های ارتقا یافته صحیح ثبت شوند
                    signal['strategy_name'] = instance.strategy_name
                    valid_signals.append(signal)

        if not valid_signals:
            logger.info(f"No valid signals found by any strategy for {symbol} {timeframe}.")
            return None

        min_rr = self.config.get("general", {}).get("min_risk_reward_ratio", 1.0)
        qualified_signals = [s for s in valid_signals if s.get('risk_reward_ratio', 0) >= min_rr]
        
        if not qualified_signals:
            logger.info(f"Signals found for {symbol} but failed R/R quality check.")
            return None
        
        best_signal = self._find_super_signal(qualified_signals)
        if not best_signal:
             priority_list = self.config.get("strategy_priority", [])
             qualified_signals.sort(key=lambda s: priority_list.index(s.get('strategy_name', '')) if s.get('strategy_name', '') in priority_list else 99)
             best_signal = qualified_signals[0]
        
        logger.info(f"Best qualified signal for {symbol} {timeframe}: {best_signal['strategy_name']} - {best_signal['direction']}")
        
        ai_confirmation = self._get_ai_confirmation(best_signal, symbol, timeframe)
        if ai_confirmation is None: # اگر AI سیگنال را وتو کند
            return None

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "base_signal": best_signal,
            "ai_confirmation": ai_confirmation,
            "full_analysis": analysis_summary
        }
