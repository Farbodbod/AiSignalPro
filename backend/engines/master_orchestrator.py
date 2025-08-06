# engines/master_orchestrator.py (v17.3 - با فیلتر کنترل کیفیت R/R)

import pandas as pd
import logging
import time
import json
from typing import Dict, Any, List, Type, Optional

from .indicator_analyzer import IndicatorAnalyzer
from .gemini_handler import GeminiHandler
from .strategies import (
    BaseStrategy, TrendRiderStrategy, MeanReversionStrategy, 
    DivergenceSniperStrategy, PivotReversalStrategy, VolumeCatalystStrategy,
    IchimokuProStrategy
)

logger = logging.getLogger(__name__)

class MasterOrchestrator:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or self._get_default_config()
        self._strategy_classes: List[Type[BaseStrategy]] = [ TrendRiderStrategy, MeanReversionStrategy, DivergenceSniperStrategy, PivotReversalStrategy, VolumeCatalystStrategy, IchimokuProStrategy ]
        self.gemini_handler = GeminiHandler()
        self.last_gemini_call_time = 0
        self.ENGINE_VERSION = "17.3.0"
        logger.info(f"MasterOrchestrator v{self.ENGINE_VERSION} (Quality Control Filter) initialized.")

    def _get_default_config(self) -> Dict[str, Any]:
        return {
            "gemini_cooldown_seconds": 300,
            "min_confluence_for_super_signal": 3,
            "min_risk_reward_ratio": 1.2, # <-- حداقل R/R قابل قبول برای TP1
            "strategy_priority": [ "SuperSignal Confluence", "DivergenceSniper", "VolumeCatalyst", "IchimokuPro", "TrendRider", "PivotReversalStrategy", "MeanReversionStrategy" ],
            'TrendRiderStrategy': { 'min_adx_strength': 25 },
            'MeanReversionStrategy': { 'rsi_oversold': 30, 'rsi_overbought': 70 },
            'DivergenceSniperStrategy': {'bullish_reversal_patterns': ['HAMMER', 'MORNINGSTAR', 'BULLISHENGULFING'],'bearish_reversal_patterns': ['SHOOTINGSTAR', 'EVENINGSTAR', 'BEARISHENGULFING'],},
            'PivotReversalStrategy': { 'proximity_percent': 0.002, 'stoch_oversold': 25, 'stoch_overbought': 75},
            'VolumeCatalystStrategy': { 'enabled': True },
            'IchimokuProStrategy': { 'min_score_to_signal': 5 },
        }

    def _find_super_signal(self, signals: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        min_confluence = self.config.get("min_confluence_for_super_signal", 3)
        buy_signals = [s for s in signals if s['direction'] == 'BUY']
        sell_signals = [s for s in signals if s['direction'] == 'SELL']
        super_direction, contributing_strategies = (None, [])
        if len(buy_signals) >= min_confluence: super_direction, contributing_strategies = ("BUY", buy_signals)
        elif len(sell_signals) >= min_confluence: super_direction, contributing_strategies = ("SELL", sell_signals)
        if not super_direction: return None
        priority_list = self.config.get("strategy_priority", [])
        contributing_strategies.sort(key=lambda s: priority_list.index(s['strategy_name']) if s['strategy_name'] in priority_list else 99)
        primary_signal = contributing_strategies[0]
        super_signal = {"strategy_name": "SuperSignal Confluence", "direction": super_direction, "entry_price": primary_signal['entry_price'], "stop_loss": primary_signal['stop_loss'], "targets": primary_signal['targets'], "risk_reward_ratio": primary_signal['risk_reward_ratio'], "confirmations": {"confluence_count": len(contributing_strategies), "contributing_strategies": [s['strategy_name'] for s in contributing_strategies]}}
        logger.info(f"🔥🔥 SUPER SIGNAL FOUND! {super_direction} with {len(contributing_strategies)} confirmations. 🔥🔥")
        return super_signal

    def _get_ai_confirmation(self, signal: Dict[str, Any], symbol: str, timeframe: str) -> Optional[Dict[str, Any]]:
        cooldown = self.config.get('gemini_cooldown_seconds', 300)
        if (time.time() - self.last_gemini_call_time) < cooldown:
            logger.info("Gemini call skipped due to cooldown.")
            return {"signal": "N/A", "confidence": 0, "explanation_fa": "AI analysis skipped due to cooldown."}
        prompt_context = { "symbol": symbol, "timeframe": timeframe, "signal_details": {k: v for k, v in signal.items() if k != 'confirmations'}, "system_reasons": signal.get('confirmations') }
        prompt = (f"You are a professional trading analyst AI. Analyze the following signal data for {symbol} on the {timeframe} timeframe. Based ONLY on the provided data, respond ONLY in JSON format with three keys: 1. 'signal' (Your confirmation: 'BUY', 'SELL', or 'HOLD'). 2. 'confidence_percent' (A number from 1 to 100 on your confidence). 3. 'explanation_fa' (A very concise, one-sentence explanation in Persian for your decision).\n\nData: {json.dumps(prompt_context, indent=2)}")
        self.last_gemini_call_time = time.time()
        ai_response = self.gemini_handler.query(prompt)
        if ai_response.get('signal') == 'HOLD':
             logger.warning(f"AI VETOED the signal for {symbol}. System signal was {signal['direction']}.")
             return None
        return ai_response

    def run_full_pipeline(self, df: pd.DataFrame, symbol: str, timeframe: str) -> Optional[Dict[str, Any]]:
        analyzer = IndicatorAnalyzer(df); analyzer.calculate_all(); analysis_summary = analyzer.get_analysis_summary()
        if len(df) >= 2: analysis_summary['price_data_prev'] = { 'close': df.iloc[-2].get('close') }
        valid_signals = []
        for sc in self._strategy_classes:
            sn, s_cfg = sc.__name__, self.config.get(sc.__name__, {})
            sig = sc(analysis_summary, s_cfg).check_signal()
            if sig: valid_signals.append(sig)
        if not valid_signals:
            logger.info(f"No valid signals found by any strategy for {symbol} {timeframe}.")
            return None

        min_rr = self.config.get("min_risk_reward_ratio", 1.0)
        qualified_signals = [s for s in valid_signals if s.get('risk_reward_ratio', 0) >= min_rr]
        if not qualified_signals:
            logger.info(f"Signals found for {symbol} but failed R/R quality check. Discarding.")
            return None
        
        best_signal = self._find_super_signal(qualified_signals)
        if not best_signal:
             priority_list = self.config.get("strategy_priority", [])
             qualified_signals.sort(key=lambda s: priority_list.index(s['strategy_name']) if s['strategy_name'] in priority_list else 99)
             best_signal = qualified_signals[0]
        
        logger.info(f"Best qualified signal for {symbol} {timeframe} selected: {best_signal['strategy_name']} - {best_signal['direction']}")
        ai_confirmation = self._get_ai_confirmation(best_signal, symbol, timeframe)
        if ai_confirmation is None: return None

        return { "symbol": symbol, "timeframe": timeframe, "base_signal": best_signal, "ai_confirmation": ai_confirmation, "full_analysis": analysis_summary }
