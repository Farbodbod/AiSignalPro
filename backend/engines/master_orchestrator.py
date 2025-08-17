# engines/master_orchestrator.py (v30.0 - Structured Logging Integration)

import pandas as pd
import logging
import time
import json
from typing import Dict, Any, List, Type, Optional, Tuple
import asyncio
import structlog # ✅ UPGRADE: Use structlog
from .indicator_analyzer import IndicatorAnalyzer
from .gemini_handler import GeminiHandler
from .strategies import *

# ✅ UPGRADE: Get logger via structlog for structured logging
logger = structlog.get_logger()

class MasterOrchestrator:
    """
    The strategic mastermind of AiSignalPro (v30.0 - Structured Logging).
    -------------------------------------------------------------------------
    This version fully integrates with the new, world-class structured logging
    system (structlog). All logging calls have been converted to a key-value
    format for enhanced observability and production monitoring, while all core
    logic, including the full Gemini prompt, remains 100% intact.
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
        self.last_gemini_call_times: Dict[str, float] = {}
        self.ENGINE_VERSION = "30.0.0"
        
        # ✅ UPGRADE: Converted to structured log
        logger.info("MasterOrchestrator initialized", version=self.ENGINE_VERSION, architecture="Fully Async")

    async def run_analysis_pipeline(self, df: pd.DataFrame, symbol: str, timeframe: str, previous_df: Optional[pd.DataFrame] = None) -> Tuple[Optional[Dict[str, Any]], Optional[pd.DataFrame]]:
        try:
            indicators_config = self.config.get('indicators', {})
            strategies_config = self.config.get('strategies', {})
            
            analyzer = IndicatorAnalyzer(df, indicators_config, strategies_config, timeframe, previous_df)
            
            await analyzer.calculate_all()
            primary_analysis = await analyzer.get_analysis_summary()
            
            return primary_analysis, analyzer.final_df
        except Exception as e:
            # ✅ UPGRADE: Converted to structured log
            logger.error("Analysis pipeline critical error", 
                         symbol=symbol, 
                         timeframe=timeframe, 
                         error=str(e), 
                         exc_info=True)
            return None, previous_df

    async def run_strategy_pipeline(self, primary_analysis: Dict[str, Any], htf_context: Dict[str, Any], symbol: str, timeframe: str) -> Optional[Dict[str, Any]]:
        valid_signals = []
        strategies_config = self.config.get('strategies', {})
        
        logger.debug("Starting strategy pipeline", symbol=symbol, timeframe=timeframe, strategies_to_run=len(self._strategy_classes))

        for sc in self._strategy_classes:
            strategy_name = sc.strategy_name
            strategy_config = strategies_config.get(strategy_name, {})
            
            if not strategy_config.get('enabled', True):
                logger.debug("Strategy disabled in config, skipping.", strategy=strategy_name)
                continue

            try:
                htf_analysis = {}
                merged_strat_config = {**sc.default_config, **strategy_config}
                
                if merged_strat_config.get('htf_confirmation_enabled'):
                    htf_map = merged_strat_config.get('htf_map', {})
                    target_htf = htf_map.get(timeframe)

                    if target_htf and target_htf != timeframe:
                        if target_htf in htf_context:
                            temp_htf_analysis = htf_context[target_htf]
                            min_rows = self.config.get("general", {}).get("min_rows_for_htf", 400)
                            htf_df = temp_htf_analysis.get('final_df')

                            if htf_df is not None and len(htf_df) >= min_rows:
                                htf_analysis = temp_htf_analysis
                            else:
                                # ✅ UPGRADE: Converted to structured log
                                logger.warning("HTF data ignored due to insufficient rows", 
                                             strategy=strategy_name, timeframe=timeframe, target_htf=target_htf, 
                                             htf_rows=len(htf_df) if htf_df is not None else 0, 
                                             min_required_rows=min_rows)
                                htf_analysis = {}
                        else:
                            # ✅ UPGRADE: Converted to structured log
                            logger.warning("Required HTF data not found in context", 
                                         strategy=strategy_name, timeframe=timeframe, target_htf=target_htf)

                instance = sc(primary_analysis, strategy_config, self.config, timeframe, symbol, htf_analysis=htf_analysis)
                signal = instance.check_signal()
                if signal:
                    signal['strategy_name'] = instance.strategy_name
                    valid_signals.append(signal)
            except Exception as e:
                # ✅ UPGRADE: Converted to structured log
                logger.error("Strategy execution error", 
                             strategy=strategy_name, 
                             timeframe=timeframe, 
                             error=str(e), 
                             exc_info=True)
        
        if not valid_signals:
            return {"status": "NEUTRAL", "message": "No strategy conditions met.", "full_analysis": primary_analysis, "engine_version": self.ENGINE_VERSION}

        min_rr = self.config.get("general", {}).get("min_risk_reward_ratio", 2.0)
        qualified_signals = [s for s in valid_signals if s.get('risk_reward_ratio', 0) >= min_rr]
        
        if not qualified_signals:
            logger.info("Signals found but failed R/R check", symbol=symbol, timeframe=timeframe, signal_count=len(valid_signals), min_rr=min_rr)
            return {"status": "NEUTRAL", "message": "Signals found but failed R/R quality check.", "full_analysis": primary_analysis, "engine_version": self.ENGINE_VERSION}
        
        best_signal = self._find_super_signal(qualified_signals)
        if not best_signal:
             priority_list = self.config.get("strategy_priority", [])
             qualified_signals.sort(key=lambda s: priority_list.index(s.get('strategy_name', '')) if s.get('strategy_name', '') in priority_list else 99)
             best_signal = qualified_signals[0]
        
        ai_confirmation = await self._get_ai_confirmation(best_signal, symbol, timeframe)
        if ai_confirmation is None:
            return {"status": "NEUTRAL", "message": "Signal was vetoed by AI or AI response was invalid.", "full_analysis": primary_analysis, "engine_version": self.ENGINE_VERSION}

        return {"status": "SUCCESS", "symbol": symbol, "timeframe": timeframe, "base_signal": best_signal, "ai_confirmation": ai_confirmation, "full_analysis": primary_analysis, "engine_version": self.ENGINE_VERSION}

    def _find_super_signal(self, signals: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        min_confluence = self.config.get("general", {}).get("min_confluence_for_super_signal", 3)
        buy_signals = [s for s in signals if s['direction'] == 'BUY']
        sell_signals = [s for s in signals if s['direction'] == 'SELL']
        
        super_direction, contributing_strategies = (None, [])
        if len(buy_signals) >= min_confluence: super_direction, contributing_strategies = ("BUY", buy_signals)
        elif len(sell_signals) >= min_confluence: super_direction, contributing_strategies = ("SELL", sell_signals)
        
        if not super_direction: return None
            
        priority_list = self.config.get("strategy_priority", [])
        contributing_strategies.sort(key=lambda s: priority_list.index(s.get('strategy_name', '')) if s.get('strategy_name', '') in priority_list else 99)
        primary_signal = contributing_strategies[0]
        
        super_signal = { "strategy_name": "SuperSignal Confluence", "direction": super_direction, "entry_price": primary_signal['entry_price'], "stop_loss": primary_signal['stop_loss'], "targets": primary_signal['targets'], "risk_reward_ratio": primary_signal['risk_reward_ratio'], "confirmations": { "confluence_count": len(contributing_strategies), "contributing_strategies": [s['strategy_name'] for s in contributing_strategies] } }
        
        # ✅ UPGRADE: Converted to structured log
        logger.info("🔥🔥 SUPER SIGNAL FOUND! 🔥🔥", 
                    direction=super_direction, 
                    confirmations=len(contributing_strategies), 
                    primary_strategy=primary_signal.get('strategy_name'),
                    contributing_strategies=[s['strategy_name'] for s in contributing_strategies])
        return super_signal

    async def _get_ai_confirmation(self, signal: Dict[str, Any], symbol: str, timeframe: str) -> Optional[Dict[str, Any]]:
        # This method's core logic and the full prompt are 100% preserved.
        cooldown = self.config.get("general", {}).get('gemini_cooldown_seconds', 300)
        last_call_time = self.last_gemini_call_times.get(symbol, 0)
        if (time.time() - last_call_time) < cooldown:
            # ✅ UPGRADE: Converted to structured log
            logger.info("Gemini call skipped due to cooldown", symbol=symbol, timeframe=timeframe)
            return {"signal": "N/A", "confidence_percent": 0, "explanation_fa": "AI analysis skipped due to per-symbol cooldown."}

        prompt_context = { "signal_details": {k: v for k, v in signal.items() if k not in ['confirmations', 'strategy_name']}, "system_strategy": signal.get('strategy_name'), "system_reasons": signal.get('confirmations') }
        json_data = json.dumps(prompt_context, indent=2, ensure_ascii=False, default=str)
        
        prompt_template = f"""
Act as a professional algorithmic trading signal validator with expertise in multi-timeframe confluence and strict JSON output. Your sole purpose is to provide a final, unbiased risk assessment.
TASK: Analyze the provided structured JSON data for a trade signal on {symbol} ({timeframe}). Validate if a high-probability trade exists.
RULES:
1.  Respond ONLY with a valid JSON object. Do not include any additional text, comments, markdown, or explanations before or after the JSON block.
2.  Your output MUST strictly follow this exact schema:
    {{
      "signal": "BUY" | "SELL" | "HOLD",
      "confidence_percent": integer (a whole number between 0 and 100, no decimals),
      "explanation_fa": string (must be a short, professional summary in PERSIAN)
    }}
3.  If your confidence is low or risks outweigh potential rewards, you MUST set "signal" to "HOLD".
4.  Your "explanation_fa" must be your own expert summary. Do NOT repeat the 'system_reasons' text verbatim. Provide a new, concise insight.
5.  If your output contains anything other than the single, valid JSON object, the system will reject it as invalid.
Here is the signal data to analyze:
{json_data}
"""
        self.last_gemini_call_times[symbol] = time.time()
        logger.debug("Querying Gemini for AI confirmation", symbol=symbol, timeframe=timeframe)
        ai_response = await asyncio.to_thread(self.gemini_handler.query, prompt_template)

        if not isinstance(ai_response, dict) or not all(k in ai_response for k in ['signal', 'confidence_percent', 'explanation_fa']):
            # ✅ UPGRADE: Converted to structured log
            logger.critical("AI response validation failed", 
                          symbol=symbol, 
                          timeframe=timeframe, 
                          invalid_response=str(ai_response)) # Use str() for safety
            return None

        if ai_response.get('signal') == 'HOLD':
            # ✅ UPGRADE: Converted to structured log
            logger.warning("AI signal vetoed", 
                         symbol=symbol, 
                         timeframe=timeframe, 
                         reason=ai_response.get('explanation_fa'))
            return None 

        logger.info("AI confirmation successful", 
                    symbol=symbol, 
                    timeframe=timeframe, 
                    ai_signal=ai_response.get('signal'),
                    ai_confidence=ai_response.get('confidence_percent'))
        return ai_response
