# engines/master_orchestrator.py (v31.2 - The Final Mandate)

import pandas as pd
import logging
import time
import json
import inspect
from typing import Dict, Any, List, Type, Optional, Tuple
import asyncio
from copy import deepcopy

from .indicator_analyzer import IndicatorAnalyzer
from .gemini_handler import GeminiHandler
from .strategies import *

logger = logging.getLogger(__name__)

class MasterOrchestrator:
    """
    The strategic mastermind of AiSignalPro (v31.2 - The Final Mandate).
    -------------------------------------------------------------------------
    This is the definitive, production-ready version. It restores the full,
    unabridged AI prompt (the "Final Mandate") to the _get_ai_confirmation
    method, ensuring the AI analyst operates with its complete and intended
    set of rules. All hardening patches from v31.1 are preserved.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._strategy_classes: List[Type[BaseStrategy]] = [
            TrendRiderPro, VwapMeanReversion, DivergenceSniperPro, PullbackSniperPro, RangeHunterPro, WhaleReversal,
            VolumeCatalystPro, BreakoutHunter, IchimokuHybridPro, ChandelierTrendRider,
            KeltnerMomentumBreakout, PivotConfluenceSniper, ConfluenceSniper,
            EmaCrossoverStrategy,
        ]
        self.gemini_handler = GeminiHandler()
        self.last_gemini_call_times: Dict[Tuple[str, str], float] = {}
        self.ENGINE_VERSION = "31.2.0"
        logger.info(f"MasterOrchestrator v{self.ENGINE_VERSION} (The Final Mandate) initialized.")

    async def run_analysis_pipeline(
        self, df: pd.DataFrame, symbol: str, timeframe: str, previous_df: Optional[pd.DataFrame] = None,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[pd.DataFrame]]:
        try:
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            missing_cols = [c for c in required_cols if c not in df.columns]
            if missing_cols:
                logger.error(f"DataFrame for {symbol}@{timeframe} missing required columns: {missing_cols}. Skipping analysis.")
                return None, previous_df
            
            if df[required_cols].isnull().values.any():
                nan_info = df[required_cols].isnull().sum()
                logger.error(f"CORRUPT DATA DETECTED for {symbol}@{timeframe}. Contains NaN values. NaN counts: {nan_info.to_dict()}")
                return None, previous_df

            indicators_config = self.config.get("indicators", {})
            strategies_config = self.config.get("strategies", {})
            
            analyzer = IndicatorAnalyzer(df, indicators_config, strategies_config, timeframe, symbol, previous_df)
            await analyzer.calculate_all()
            primary_analysis = await analyzer.get_analysis_summary()
            return primary_analysis, analyzer.final_df
        except Exception as e:
            logger.error(f"Critical error in ANALYSIS pipeline for {symbol}@{timeframe}: {e}", exc_info=True)
            return None, previous_df

    async def run_strategy_pipeline(
        self, primary_analysis: Dict[str, Any], htf_context: Dict[str, Any], symbol: str, timeframe: str,
    ) -> Optional[Dict[str, Any]]:
        if not isinstance(primary_analysis, dict):
            logger.error(f"Primary analysis for {symbol}@{timeframe} is invalid (not a dict). Skipping strategies.")
            return {"status": "NEUTRAL", "message": "Invalid primary analysis package."}

        valid_signals = []
        strategies_config = self.config.get("strategies", {})
        for sc in self._strategy_classes:
            strategy_name = sc.strategy_name
            strategy_config = strategies_config.get(strategy_name, {})
            if not strategy_config.get("enabled", True): continue
            
            try:
                htf_analysis = {}
                merged_strat_config = {**getattr(sc, "default_config", {}), **strategy_config}
                if merged_strat_config.get("htf_confirmation_enabled"):
                    htf_map = merged_strat_config.get("htf_map", {})
                    target_htf = htf_map.get(timeframe)
                    if target_htf and target_htf != timeframe:
                        if target_htf in htf_context:
                            temp_htf_analysis = htf_context[target_htf]
                            min_rows = self.config.get("general", {}).get("min_rows_for_htf", 300)
                            htf_df = temp_htf_analysis.get("final_df")
                            rows_info = len(htf_df) if isinstance(htf_df, pd.DataFrame) else "invalid/None"
                            if isinstance(htf_df, pd.DataFrame) and len(htf_df) >= min_rows:
                                htf_analysis = temp_htf_analysis
                            else:
                                logger.warning(f"Strategy '{strategy_name}' on {timeframe} ignored HTF data for '{target_htf}' because it had too few rows ({rows_info}) or was invalid.")
                        else:
                            logger.warning(f"Strategy '{strategy_name}' on {timeframe} requires HTF data for '{target_htf}', but it was not found.")
                
                isolated_primary_analysis = deepcopy(primary_analysis)
                isolated_htf_analysis = deepcopy(htf_analysis)
                instance = sc(isolated_primary_analysis, strategy_config, self.config, timeframe, symbol, htf_analysis=isolated_htf_analysis)
                signal = instance.check_signal()

                if signal:
                    signal["strategy_name"] = instance.strategy_name
                    if "risk_reward_ratio" not in signal:
                        logger.debug(f"Strategy '{strategy_name}' signal has no 'risk_reward_ratio'. Defaulting to 0.")
                    valid_signals.append(signal)
            except Exception as e:
                logger.error(f"Error running strategy '{strategy_name}' on {timeframe}: {e}", exc_info=True)
        
        if not valid_signals: return {"status": "NEUTRAL", "message": "No strategy conditions met.", "full_analysis": primary_analysis, "engine_version": self.ENGINE_VERSION}
        min_rr = self.config.get("general", {}).get("min_risk_reward_ratio", 2.0); qualified_signals = [s for s in valid_signals if s.get("risk_reward_ratio", 0) >= min_rr]
        if not qualified_signals: return {"status": "NEUTRAL", "message": "Signals found but failed R/R quality check.", "full_analysis": primary_analysis, "engine_version": self.ENGINE_VERSION}
        
        best_signal = self._find_super_signal(qualified_signals)
        if not best_signal:
            priority_list = self.config.get("strategy_priority", []); qualified_signals.sort(key=lambda s: priority_list.index(s.get("strategy_name")) if s.get("strategy_name") in priority_list else 99); best_signal = qualified_signals[0]

        ai_confirmation = await self._get_ai_confirmation(best_signal, symbol, timeframe)
        if ai_confirmation is None: return {"status": "NEUTRAL", "message": "Signal was vetoed by AI or AI response was invalid.", "full_analysis": primary_analysis, "engine_version": self.ENGINE_VERSION}

        return {"status": "SUCCESS", "symbol": symbol, "timeframe": timeframe, "base_signal": best_signal, "ai_confirmation": ai_confirmation, "full_analysis": primary_analysis, "engine_version": self.ENGINE_VERSION}

    def _find_super_signal(self, signals: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        min_confluence = self.config.get("general", {}).get("min_confluence_for_super_signal", 3); buy_signals = [s for s in signals if s.get("direction") == "BUY"]; sell_signals = [s for s in signals if s.get("direction") == "SELL"]; super_direction, contributing_strategies = (None, [])
        if len(buy_signals) >= min_confluence: super_direction, contributing_strategies = ("BUY", buy_signals)
        elif len(sell_signals) >= min_confluence: super_direction, contributing_strategies = ("SELL", sell_signals)
        if not super_direction: return None
        
        priority_list = self.config.get("strategy_priority", []); contributing_strategies.sort(key=lambda s: priority_list.index(s.get("strategy_name")) if s.get("strategy_name") in priority_list else 99); primary_signal = contributing_strategies[0]
        super_signal = {
            "strategy_name": "SuperSignal Confluence", "direction": super_direction,
            "entry_price": primary_signal.get("entry_price"), "stop_loss": primary_signal.get("stop_loss"),
            "targets": primary_signal.get("targets"), "risk_reward_ratio": primary_signal.get("risk_reward_ratio"),
            "confirmations": {"confluence_count": len(contributing_strategies), "contributing_strategies": [s.get("strategy_name") for s in contributing_strategies]}
        }
        logger.info(f"🔥🔥 SUPER SIGNAL FOUND! {super_direction} with {len(contributing_strategies)} confirmations. 🔥🔥")
        return super_signal

    async def _get_ai_confirmation(self, signal: Dict[str, Any], symbol: str, timeframe: str) -> Optional[Dict[str, Any]]:
        cooldown_key = (symbol, timeframe); cooldown = self.config.get("general", {}).get("gemini_cooldown_seconds", 300); last_call_time = self.last_gemini_call_times.get(cooldown_key, 0)
        if (time.time() - last_call_time) < cooldown:
            logger.info(f"Gemini call for {symbol}@{timeframe} skipped due to cooldown."); return {"signal": "N/A", "confidence_percent": 0, "explanation_fa": "AI analysis skipped due to per-symbol cooldown."}
        
        prompt_context = {"signal_details": {k: v for k, v in signal.items() if k not in ["confirmations", "strategy_name"]}, "system_strategy": signal.get("strategy_name"), "system_reasons": signal.get("confirmations")}
        json_data = json.dumps(prompt_context, indent=2, ensure_ascii=False, default=str)
        
        # ✅ THE FINAL MANDATE: Restored the full, unabridged AI prompt.
        prompt_template = f"""
Act as a professional algorithmic trading signal validator with expertise in multi-timeframe confluence and strict JSON output. Your sole purpose is to provide a final, unbiased risk assessment.
TASK: Analyze the provided structured JSON data for a trade signal on {symbol} ({timeframe}). Validate if a high-probability trade exists.
RULES:
1.  Respond ONLY with a valid JSON object. Do not include any additional text, comments, markdown, or explanations before or after the JSON block.
2.  Your output MUST strictly follow this exact schema. CRITICAL: The key for confidence MUST be "confidence_percent". Do NOT use "confidence".
    {{
      "signal": "BUY" | "SELL" | "HOLD",
      "confidence_percent": integer (a whole number between 0 and 100, no decimals),
      "explanation_fa": string (must be a short, professional summary in PERSIAN)
    }}
3.  If your confidence is low or risks outweigh potential rewards, you MUST set "signal" to "HOLD". A HOLD is a veto.
4.  Your "explanation_fa" must be your own expert summary. Do NOT repeat the 'system_reasons' text verbatim. Provide a new, concise insight based on the data.
5.  Base your decision on a holistic view. A strong trend confirmation (e.g., ADX) might be more important than a minor oscillator signal. A good R/R is crucial.
6.  If your output contains anything other than the single, valid JSON object, the system will reject it as invalid.
Here is the signal data to analyze:
{json_data}
"""
        try:
            gemini_query_method = self.gemini_handler.query
            if inspect.iscoroutinefunction(gemini_query_method): ai_response = await gemini_query_method(prompt_template)
            else: ai_response = await asyncio.to_thread(gemini_query_method, prompt_template)
            self.last_gemini_call_times[cooldown_key] = time.time()
        except Exception as e:
            logger.error(f"Gemini API call failed for {symbol}@{timeframe}: {e}")
            return None
        
        try:
            if not isinstance(ai_response, dict): raise TypeError("Response is not a dictionary.")
            validated_signal = str(ai_response["signal"])
            if validated_signal.upper() not in ["BUY", "SELL", "HOLD"]: raise ValueError(f"Invalid signal value: {validated_signal}")
            confidence_val = ai_response.get("confidence_percent")
            if confidence_val is None: confidence_val = ai_response.get("confidence")
            if confidence_val is None: raise KeyError("Missing 'confidence_percent' or 'confidence' key.")
            validated_confidence = int(confidence_val)
            if not (0 <= validated_confidence <= 100): raise ValueError(f"Confidence out of range: {validated_confidence}")
            if "explanation_fa" not in ai_response: raise KeyError("Missing 'explanation_fa' key.")
        except (TypeError, ValueError, KeyError, AttributeError) as e:
            logger.critical(f"FATAL: AI response schema validation failed for {symbol}@{timeframe}. Error: {e}. Response: {ai_response}")
            return None
        
        if validated_signal.upper() == "HOLD":
            logger.warning(f"AI VETOED for {symbol}@{timeframe}. Reason: {ai_response.get('explanation_fa')}")
            return None
        
        return ai_response
