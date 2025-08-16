# engines/master_orchestrator.py (v28.0 - Focus Mode Integration)

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
    The strategic mastermind of AiSignalPro (v28.0 - Focus Mode Integration).
    This version is updated to pass the symbol name to each strategy instance,
    enabling the BaseStrategy's "Focus Mode" logging feature. It also includes
    the HTF Quality Gate.
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
        self.ENGINE_VERSION = "28.0.0"
        
        logger.info(f"MasterOrchestrator v{self.ENGINE_VERSION} (Focus Mode Integration) initialized.")

    def run_analysis_pipeline(self, df: pd.DataFrame, symbol: str, timeframe: str, previous_df: Optional[pd.DataFrame] = None) -> Tuple[Optional[Dict[str, Any]], Optional[pd.DataFrame]]:
        # This method remains unchanged.
        try:
            indicators_config = self.config.get('indicators', {})
            strategies_config = self.config.get('strategies', {})
            
            analyzer = IndicatorAnalyzer(df, indicators_config, strategies_config, timeframe, previous_df)
            analyzer.calculate_all()
            primary_analysis = analyzer.get_analysis_summary()
            
            return primary_analysis, analyzer.final_df
        except Exception as e:
            logger.error(f"Critical error in ANALYSIS pipeline for {symbol}@{timeframe}: {e}", exc_info=True)
            return None, previous_df

    def run_strategy_pipeline(self, primary_analysis: Dict[str, Any], htf_context: Dict[str, Any], symbol: str, timeframe: str) -> Optional[Dict[str, Any]]:
        valid_signals = []
        strategies_config = self.config.get('strategies', {})

        for sc in self._strategy_classes:
            strategy_name = sc.strategy_name
            strategy_config = strategies_config.get(strategy_name, {})
            
            if not strategy_config.get('enabled', True): continue

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
                                logger.debug(f"Strategy '{strategy_name}' on {timeframe} accessed valid HTF data ({len(htf_df)} rows) for {target_htf}.")
                            else:
                                logger.warning(f"Strategy '{strategy_name}' on {timeframe} ignored HTF data for '{target_htf}' because it had too few rows ({len(htf_df) if htf_df is not None else 0} < {min_rows}).")
                                htf_analysis = {}
                        else:
                            logger.warning(f"Strategy '{strategy_name}' on {timeframe} requires HTF data for '{target_htf}', but it was not found in the global context.")

                # ✅ CHANGE: Pass the 'symbol' to the strategy constructor
                instance = sc(primary_analysis, strategy_config, self.config, timeframe, symbol, htf_analysis=htf_analysis)
                signal = instance.check_signal()
                if signal:
                    signal['strategy_name'] = instance.strategy_name
                    valid_signals.append(signal)
            except Exception as e:
                logger.error(f"Error running strategy '{strategy_name}' on {timeframe}: {e}", exc_info=True)
        
        # --- The rest of the function remains unchanged ---
        if not valid_signals:
            return {"status": "NEUTRAL", "message": "No strategy conditions met.", "full_analysis": primary_analysis, "engine_version": self.ENGINE_VERSION}

        min_rr = self.config.get("general", {}).get("min_risk_reward_ratio", 2.0)
        qualified_signals = [s for s in valid_signals if s.get('risk_reward_ratio', 0) >= min_rr]
        
        if not qualified_signals:
            return {"status": "NEUTRAL", "message": "Signals found but failed R/R quality check.", "full_analysis": primary_analysis, "engine_version": self.ENGINE_VERSION}
        
        best_signal = self._find_super_signal(qualified_signals)
        if not best_signal:
             priority_list = self.config.get("strategy_priority", [])
             qualified_signals.sort(key=lambda s: priority_list.index(s.get('strategy_name', '')) if s.get('strategy_name', '') in priority_list else 99)
             best_signal = qualified_signals[0]
        
        ai_confirmation = self._get_ai_confirmation(best_signal, symbol, timeframe)
        if ai_confirmation is None:
            return {"status": "NEUTRAL", "message": "Signal was vetoed by AI or AI response was invalid.", "full_analysis": primary_analysis, "engine_version": self.ENGINE_VERSION}

        return {"status": "SUCCESS", "symbol": symbol, "timeframe": timeframe, "base_signal": best_signal, "ai_confirmation": ai_confirmation, "full_analysis": primary_analysis, "engine_version": self.ENGINE_VERSION}

    def _find_super_signal(self, signals: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        # This function remains unchanged.
        min_confluence, buy_signals, sell_signals = self.config.get("general", {}).get("min_confluence_for_super_signal", 3), [], []
        for s in signals:
            if s['direction'] == 'BUY': buy_signals.append(s)
            elif s['direction'] == 'SELL': sell_signals.append(s)
        
        super_direction, contributing_strategies = (None, [])
        if len(buy_signals) >= min_confluence: super_direction, contributing_strategies = ("BUY", buy_signals)
        elif len(sell_signals) >= min_confluence: super_direction, contributing_strategies = ("SELL", sell_signals)
        
        if not super_direction: return None
            
        priority_list = self.config.get("strategy_priority", [])
        contributing_strategies.sort(key=lambda s: priority_list.index(s.get('strategy_name', '')) if s.get('strategy_name', '') in priority_list else 99)
        primary_signal = contributing_strategies[0]
        
        super_signal = { "strategy_name": "SuperSignal Confluence", "direction": super_direction, "entry_price": primary_signal['entry_price'], "stop_loss": primary_signal['stop_loss'], "targets": primary_signal['targets'], "risk_reward_ratio": primary_signal['risk_reward_ratio'], "confirmations": { "confluence_count": len(contributing_strategies), "contributing_strategies": [s['strategy_name'] for s in contributing_strategies] } }
        logger.info(f"🔥🔥 SUPER SIGNAL FOUND! {super_direction} with {len(contributing_strategies)} confirmations. 🔥🔥")
        return super_signal

    def _get_ai_confirmation(self, signal: Dict[str, Any], symbol: str, timeframe: str) -> Optional[Dict[str, Any]]:
        # This function remains unchanged.
        cooldown = self.config.get("general", {}).get('gemini_cooldown_seconds', 300)
        last_call_time = self.last_gemini_call_times.get(symbol, 0)
        if (time.time() - last_call_time) < cooldown:
            logger.info(f"Gemini call for {symbol} skipped due to cooldown.")
            return {"signal": "N/A", "confidence_percent": 0, "explanation_fa": "AI analysis skipped due to per-symbol cooldown."}
        prompt_context = { "signal_details": {k: v for k, v in signal.items() if k not in ['confirmations', 'strategy_name']}, "system_strategy": signal.get('strategy_name'), "system_reasons": signal.get('confirmations') }
        json_data = json.dumps(prompt_context, indent=2, ensure_ascii=False, default=str)
        prompt_template = f"""
Act as a professional algorithmic trading signal validator...
""" # Prompt truncated for brevity
        self.last_gemini_call_times[symbol] = time.time()
        ai_response = self.gemini_handler.query(prompt_template)
        if not isinstance(ai_response, dict) or not all(k in ai_response for k in ['signal', 'confidence_percent', 'explanation_fa']):
            logger.critical(f"FATAL: AI response validation failed. Response format was invalid. Response: {ai_response}")
            return None
        if ai_response.get('signal') == 'HOLD':
            logger.warning(f"AI VETOED the signal for {symbol}. System signal was {signal['direction']}. Reason: {ai_response.get('explanation_fa')}")
            return None 
        return ai_response

