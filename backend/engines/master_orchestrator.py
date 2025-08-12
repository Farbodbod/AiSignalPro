import pandas as pd
import logging
import time
import json
from typing import Dict, Any, List, Type, Optional, Tuple

from .indicator_analyzer import IndicatorAnalyzer
from .gemini_handler import GeminiHandler
from .strategies import *

logger = logging.getLogger(__name__)

class MasterOrchestrator:
    """
    The strategic mastermind of the AiSignalPro project (v23.0 - Stateful Edition)
    This version accepts the previous analysis state to enable high-performance,
    incremental calculations, reducing redundant computations by over 95%.
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._strategy_classes: List[Type[BaseStrategy]] = [
            TrendRiderPro, VwapMeanReversion, DivergenceSniperPro, WhaleReversal,
            VolumeCatalystPro, BreakoutHunter, IchimokuHybridPro, ChandelierTrendRider,
            KeltnerMomentumBreakout, PivotConfluenceSniper, ConfluenceSniper,
            EmaCrossoverStrategy,
        ]
        self.gemini_handler = GeminiHandler()
        self.last_gemini_call_time = 0
        self.ENGINE_VERSION = "23.0.0"
        
        logger.info(f"MasterOrchestrator v{self.ENGINE_VERSION} (Legendary & Stateful) initialized.")

    def _find_super_signal(self, signals: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
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
        cooldown = self.config.get("general", {}).get('gemini_cooldown_seconds', 300)
        if (time.time() - self.last_gemini_call_time) < cooldown:
            logger.info("Gemini call skipped due to cooldown.")
            return {"signal": "N/A", "confidence_percent": 0, "explanation_fa": "AI analysis skipped due to cooldown."}

        prompt_context = {
            "signal_details": {k: v for k, v in signal.items() if k not in ['confirmations', 'strategy_name']},
            "system_strategy": signal.get('strategy_name'),
            "system_reasons": signal.get('confirmations')
        }
        
        json_data = json.dumps(prompt_context, indent=2, ensure_ascii=False, default=str)
        
        prompt_template = f"""
شما یک تحلیلگر ارشد و معامله‌گر کوانت (Quantitative Trader) با سال‌ها تجربه در بازارهای ارز دیجیتال هستید. شما به تحلیل‌های مبتنی بر داده، ساختار بازار و مدیریت ریسک تسلط کامل دارید.

سیستم معاملاتی الگوریتمی ما یک سیگنال اولیه برای {symbol} در تایم فریم {timeframe} صادر کرده است. وظیفه شما این است که مانند یک مدیر ریسک یا یک تحلیلگر دوم، این سیگنال را به صورت مستقل و نقادانه ارزیابی کنید. ما تمام داده‌های تکنیکالی که منجر به این سیگنال شده‌اند را در اختیار شما قرار می‌دهیم.

**وظایف شما:**
۱. **ارزیابی همه‌جانبه:** تمام داده‌ها را بررسی کنید. به دنبال **تلاقی (Confluence)** بین دلایل مختلف بگردید. آیا دلایل سیستم با هم همخوانی دارند؟ آیا نقاط ضعفی در این سیگنال می‌بینید؟ (مثلاً واگرایی ضعیف، حجم کم در شکست، یا نزدیکی به یک سطح قوی مخالف).

۲. **تصمیم‌گیری نهایی، توضیح کارشناسی و امتیازدهی:** بر اساس تحلیل خود، یک پاسخ **فقط در فرمت JSON** با سه کلید زیر ارائه دهید:
   - `signal`: تصمیم نهایی شما: 'BUY' (تایید سیگنال خرید)، 'SELL' (تایید سیگنال فروش)، یا 'HOLD' (رد کردن سیگنال به دلیل ریسک بالا یا شواهد ناکافی).
   - `confidence_percent`: یک امتیاز اطمینان عددی بین ۱ تا ۱۰۰ به تصمیم خود اختصاص دهید. این امتیاز باید منعکس‌کننده میزان همسویی و قدرت داده‌های تکنیکال باشد.
   - `explanation_fa`: یک توضیح مختصر اما بسیار حرفه‌ای (۲ تا ۳ جمله) به زبان فارسی. در این توضیح، **صرفاً دلایل سیستم را تکرار نکنید،** بلکه **نتیجه‌گیری و تحلیل خودتان** را بیان کنید. برای مثال: 'با توجه به تلاقی مقاومت ساختاری و اشباع خرید در چندین اسیلاتور، پتانسیل بازگشت نزولی بسیار بالاست و سیگنال فروش تایید می‌شود.'

**داده‌های تحلیل:**
{json_data}
"""
        self.last_gemini_call_time = time.time()
        ai_response = self.gemini_handler.query(prompt_template)

        if ai_response.get('signal') == 'HOLD':
            logger.warning(f"AI VETOED the signal for {symbol}. System signal was {signal['direction']}. Reason: {ai_response.get('explanation_fa')}")
            return None 
        
        if "confidence_percent" not in ai_response and "confidence" in ai_response:
             ai_response["confidence_percent"] = ai_response.pop("confidence")

        return ai_response

    def run_full_pipeline(self, df: pd.DataFrame, symbol: str, timeframe: str, previous_df: Optional[pd.DataFrame] = None) -> Tuple[Dict[str, Any], Optional[pd.DataFrame]]:
        analyzer = IndicatorAnalyzer(df, config=self.config.get('indicators', {}), timeframe=timeframe, previous_df=previous_df)
        analyzer.calculate_all()
        
        primary_analysis = analyzer.get_analysis_summary()
        
        htf_timeframe = '4h'
        min_htf_rows = self.config.get("general", {}).get("min_rows_for_htf", 300)

        if timeframe == htf_timeframe:
            htf_analysis = primary_analysis
        elif len(analyzer.final_df) < min_htf_rows:
            logger.warning(f"Skipping HTF analysis for {symbol}. Insufficient combined data rows: {len(analyzer.final_df)} < {min_htf_rows}")
            htf_analysis = {}
        else:
            logger.info(f"Running HTF analysis for {symbol} on {htf_timeframe}...")
            htf_analyzer = IndicatorAnalyzer(df, config=self.config.get('indicators', {}), timeframe=htf_timeframe)
            htf_analyzer.calculate_all()
            htf_analysis = htf_analyzer.get_analysis_summary()
        
        valid_signals = []
        strategy_configs = self.config.get('strategies', {})
        for sc in self._strategy_classes:
            strategy_name = sc.strategy_name
            strategy_config = strategy_configs.get(strategy_name, {})
            if strategy_config.get('enabled', True):
                try:
                    instance = sc(primary_analysis, strategy_config, timeframe, htf_analysis=htf_analysis)
                    signal = instance.check_signal()
                    if signal:
                        signal['strategy_name'] = instance.strategy_name
                        valid_signals.append(signal)
                except Exception as e:
                    logger.error(f"Error running strategy '{strategy_name}' on {timeframe}: {e}", exc_info=True)
        
        if not valid_signals:
            result = {"status": "NEUTRAL", "message": "No strategy conditions met.", "full_analysis": primary_analysis, "engine_version": self.ENGINE_VERSION}
            return result, analyzer.final_df

        min_rr = self.config.get("general", {}).get("min_risk_reward_ratio", 2.0)
        qualified_signals = [s for s in valid_signals if s.get('risk_reward_ratio', 0) >= min_rr]
        
        if not qualified_signals:
            result = {"status": "NEUTRAL", "message": "Signals found but failed R/R quality check.", "full_analysis": primary_analysis, "engine_version": self.ENGINE_VERSION}
            return result, analyzer.final_df
        
        best_signal = self._find_super_signal(qualified_signals)
        if not best_signal:
             priority_list = self.config.get("strategy_priority", [])
             qualified_signals.sort(key=lambda s: priority_list.index(s.get('strategy_name', '')) if s.get('strategy_name', '') in priority_list else 99)
             best_signal = qualified_signals[0]
        
        ai_confirmation = self._get_ai_confirmation(best_signal, symbol, timeframe)
        if ai_confirmation is None:
            result = {"status": "NEUTRAL", "message": "Signal was vetoed by AI analysis.", "full_analysis": primary_analysis, "engine_version": self.ENGINE_VERSION}
            return result, analyzer.final_df

        final_package = {"status": "SUCCESS", "symbol": symbol, "timeframe": timeframe, "base_signal": best_signal, "ai_confirmation": ai_confirmation, "full_analysis": primary_analysis, "engine_version": self.ENGINE_VERSION}
        return final_package, analyzer.final_df
