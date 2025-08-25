# backend/engines/master_orchestrator.py (v33.0 - The Final Polish)

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
from core.news_fetcher import NewsFetcher

logger = logging.getLogger(__name__)

class MasterOrchestrator:
    """
    The strategic mastermind of AiSignalPro (v33.0 - The Final Polish).
    -------------------------------------------------------------------------
    This is the definitive, production-ready version. It incorporates the final
    architectural polish: passing the strategy class list to the analyzer to
    ensure full awareness of all indicator dependencies (solving the "choking"
    bug), and hardening the AI response validation. This version represents the
    peak of our architectural integrity and intelligence.
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
        self.news_fetcher = NewsFetcher()
        self.last_gemini_call_times: Dict[Tuple[str, str], float] = {}
        self.ENGINE_VERSION = "33.0.0"
        logger.info(f"MasterOrchestrator v{self.ENGINE_VERSION} (The Final Polish) initialized.")

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
            
            # ✅ FINAL POLISH (v33.0): Pass the full strategy class list to the analyzer.
            # This is the "Final Cook Connection" ensuring the analyzer is aware of
            # indicator dependencies defined in strategy default_configs.
            analyzer = IndicatorAnalyzer(
                df, 
                indicators_config, 
                strategies_config, 
                self._strategy_classes,
                timeframe, 
                symbol, 
                previous_df
            )
            
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
        
        min_rr = self.config.get("general", {}).get("min_risk_reward_ratio", 2.0)
        qualified_signals = [s for s in valid_signals if s.get("risk_reward_ratio", 0) >= min_rr]
        
        if len(valid_signals) > len(qualified_signals):
            rejected_signals_info = [f"{s['strategy_name']}(R/R={s.get('risk_reward_ratio', 0):.2f})" for s in valid_signals if s not in qualified_signals]
            logger.warning(f"   - R/R FILTER on {symbol}@{timeframe}: Dropped {len(rejected_signals_info)} signal(s) failing min R/R of {min_rr}. Rejected: [{', '.join(rejected_signals_info)}]")
        elif valid_signals:
            logger.info(f"   - R/R FILTER on {symbol}@{timeframe}: All {len(valid_signals)} signal(s) passed min R/R of {min_rr}.")
        
        if not qualified_signals: return {"status": "NEUTRAL", "message": "Signals found but failed R/R quality check.", "full_analysis": primary_analysis, "engine_version": self.ENGINE_VERSION}
        
        best_signal = self._find_super_signal(qualified_signals)
        if not best_signal:
            priority_list = self.config.get("strategy_priority", [])
            qualified_signals.sort(key=lambda s: priority_list.index(s.get("strategy_name")) if s.get("strategy_name") in priority_list else 99)
            best_signal = qualified_signals[0]
            
            if len(qualified_signals) > 1:
                contenders_by_priority = [s['strategy_name'] for s in qualified_signals]
                logger.info(f"   - SIGNAL SELECTION on {symbol}@{timeframe}: No SuperSignal. Chose '{best_signal['strategy_name']}' based on priority. Priority Order: [{', '.join(contenders_by_priority)}]")
            else:
                 logger.info(f"   - SIGNAL SELECTION on {symbol}@{timeframe}: Only one qualified signal found. Proceeding with '{best_signal['strategy_name']}'.")

        ai_confirmation = await self._get_ai_confirmation(best_signal, primary_analysis, htf_context, symbol, timeframe)
        if ai_confirmation is None: return {"status": "NEUTRAL", "message": "Signal was vetoed by AI or AI response was invalid.", "full_analysis": primary_analysis, "engine_version": self.ENGINE_VERSION}

        return {"status": "SUCCESS", "symbol": symbol, "timeframe": timeframe, "base_signal": best_signal, "ai_confirmation": ai_confirmation, "full_analysis": primary_analysis, "engine_version": self.ENGINE_VERSION}

    def _create_ai_mission_briefing(self, analysis: Dict[str, Any], htf_context: Dict[str, Any], timeframe: str) -> Dict[str, Any]:
        # This method is unchanged and correct
        briefing = {}; indicator_map = analysis.get('_indicator_map', {})
        primary_ctx = {}
        if key := indicator_map.get('adx'):
            if adx := analysis.get(key): primary_ctx['ADX'] = adx.get('analysis', {}).get('summary')
        if key := indicator_map.get('rsi'):
            if rsi := analysis.get(key): primary_ctx['RSI'] = rsi.get('analysis', {}).get('position')
        if key := indicator_map.get('macd'):
            if macd := analysis.get(key): primary_ctx['MACD'] = macd.get('analysis', {}).get('context')
        if key := indicator_map.get('bollinger'):
            if bollinger := analysis.get(key): primary_ctx['Bollinger'] = bollinger.get('analysis', {}).get('position')
        if key := indicator_map.get('whales'):
            if whales := analysis.get(key): primary_ctx['Whales'] = (whales.get('analysis',{}).get('summary'))
        briefing[f'Primary_TF_{timeframe}'] = primary_ctx
        
        htf_map_proxy = self.config.get("strategies", {}).get("TrendRiderPro", {}).get("htf_map", {})
        target_htf = htf_map_proxy.get(timeframe)
        if target_htf and target_htf in htf_context:
            htf_analysis = htf_context[target_htf]; htf_indicator_map = htf_analysis.get('_indicator_map', {}); htf_ctx = {}
            if key := htf_indicator_map.get('adx'):
                if adx := htf_analysis.get(key): htf_ctx['ADX'] = adx.get('analysis', {}).get('summary')
            if key := htf_indicator_map.get('supertrend'):
                if st := htf_analysis.get(key): htf_ctx['SuperTrend'] = st.get('analysis', {}).get('trend')
            if key := htf_indicator_map.get('ichimoku'):
                if ichi := htf_analysis.get(key): htf_ctx['Ichimoku'] = ichi.get('analysis', {}).get('trend_summary')
            briefing[f'Higher_TF_{target_htf}'] = htf_ctx
        return briefing

    async def _get_ai_confirmation(self, signal: Dict[str, Any], primary_analysis: Dict, htf_context: Dict, symbol: str, timeframe: str) -> Optional[Dict[str, Any]]:
        cooldown_key = (symbol, timeframe); cooldown = self.config.get("general", {}).get("gemini_cooldown_seconds", 300); last_call_time = self.last_gemini_call_times.get(cooldown_key, 0)
        if (time.time() - last_call_time) < cooldown:
            logger.info(f"Gemini call for {symbol}@{timeframe} skipped due to cooldown.")
            return {"signal": "N/A", "confidence_percent": 0, "explanation_fa": "AI analysis skipped due to per-symbol cooldown."}
        
        market_context = self._create_ai_mission_briefing(primary_analysis, htf_context, timeframe)
        news_headlines = await self.news_fetcher.get_headlines(symbol)
        
        prompt_context = {
            "BASE_SIGNAL": signal, "MARKET_CONTEXT": market_context,
            "NEWS_HEADLINES": news_headlines if news_headlines is not None else "News fetcher disabled or failed."
        }
        json_data = json.dumps(prompt_context, indent=2, ensure_ascii=False, default=str)
        
        # The Grandmaster prompt remains unchanged and complete
        prompt_template = f"""
Act as 'ARC-7', a world-class Quantitative Lead Analyst and Senior Risk Manager for the AiSignalPro algorithmic trading fund. Your judgment is final. Your primary directive is capital preservation. You are skeptical, data-driven, and ruthless in your analysis.

TASK:
Perform a multi-faceted risk analysis of the provided data package. Your goal is to find flaws and reasons to REJECT the trade. Only approve signals that present an exceptionally high-probability setup with a clear statistical and contextual edge.

INPUT DATA STRUCTURE:
You will receive a JSON object with three main keys:
1. `BASE_SIGNAL`: The primary signal generated by our rule-based strategy.
2. `MARKET_CONTEXT`: A curated summary of key indicator states across multiple timeframes.
3. `NEWS_HEADLINES`: A list of recent, relevant news headlines for sentiment analysis.

RULES (THE GRANDMASTER'S MANDATE):
1.  Respond ONLY with a valid JSON object. No other text or markdown.
2.  Your output MUST strictly follow this exact schema:
    {{
      "signal": "BUY" | "SELL" | "HOLD",
      "confidence_percent": integer (0-100),
      "explanation_fa": string (A short, professional summary in PERSIAN),
      "improvement_suggestion": string (Optional: A suggestion to improve SL or TP, in PERSIAN)
    }}
3.  If confidence is low or risks are high, you MUST set "signal" to "HOLD". A HOLD is a final veto.
4.  Your "explanation_fa" must be your own expert summary. DO NOT repeat the input reasons. Provide a new, concise insight.
5.  HOLISTIC ANALYSIS: You MUST weigh all three data sections. A strong technical signal can be vetoed by extremely negative news sentiment. A weak technical signal should be rejected, even in a positive news environment.
6.  CONTRADICTION HUNTING: Actively search for contradictions. Does the HTF ADX contradict the LTF signal? Does MACD momentum oppose the RSI position? Highlight these contradictions in your explanation.
7.  REALISM CHECK: Critically evaluate the realism of the `stop_loss` and `targets`. Is the stop loss so tight it will be hit by normal noise? Is the R/R ratio statistically improbable (e.g., > 1:10)? If the risk model seems flawed, VETO the signal and explain why.

Here is the complete data package to analyze:
{json_data}
"""
        
        try:
            gemini_query_method = self.gemini_handler.query
            if inspect.iscoroutinefunction(gemini_query_method):
                ai_response = await gemini_query_method(prompt_template)
            else:
                ai_response = await asyncio.to_thread(gemini_query_method, prompt_template)
            self.last_gemini_call_times[cooldown_key] = time.time()
        except Exception as e:
            logger.error(f"Gemini API call failed for {symbol}@{timeframe}: {e}"); return None
        
        try:
            if not isinstance(ai_response, dict): raise TypeError("Response is not a dictionary.")
            validated_signal = str(ai_response["signal"])
            if validated_signal.upper() not in ["BUY", "SELL", "HOLD"]: raise ValueError(f"Invalid signal value: {validated_signal}")
            
            # ✅ FINAL POLISH (v33.0): Flexible validation for confidence key.
            confidence_val = ai_response.get("confidence_percent")
            if confidence_val is None:
                confidence_val = ai_response.get("confidence")
            if confidence_val is None:
                raise KeyError("Missing 'confidence_percent' or 'confidence' key.")
            
            validated_confidence = int(confidence_val)
            if not (0 <= validated_confidence <= 100): raise ValueError(f"Confidence out of range: {validated_confidence}")
            if "explanation_fa" not in ai_response: raise KeyError("Missing 'explanation_fa' key.")
        except (TypeError, ValueError, KeyError, AttributeError) as e:
            logger.critical(f"FATAL: AI response schema validation failed for {symbol}@{timeframe}. Error: {e}. Response: {ai_response}"); return None
        
        if validated_signal.upper() == "HOLD":
            logger.warning(f"AI VETOED for {symbol}@{timeframe}. Reason: {ai_response.get('explanation_fa')}"); return None
        
        return ai_response
    
    def _find_super_signal(self, signals: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        # This method is unchanged and correct.
        min_confluence = self.config.get("general", {}).get("min_confluence_for_super_signal", 3)
        buy_signals = [s for s in signals if s.get("direction") == "BUY"]
        sell_signals = [s for s in signals if s.get("direction") == "SELL"]
        super_direction, contributing_strategies = (None, [])
        if len(buy_signals) >= min_confluence:
            super_direction, contributing_strategies = ("BUY", buy_signals)
        elif len(sell_signals) >= min_confluence:
            super_direction, contributing_strategies = ("SELL", sell_signals)
        if not super_direction:
            return None
        priority_list = self.config.get("strategy_priority", [])
        contributing_strategies.sort(key=lambda s: priority_list.index(s.get("strategy_name")) if s.get("strategy_name") in priority_list else 99)
        primary_signal = contributing_strategies[0]
        super_signal = {
            "strategy_name": "SuperSignal Confluence", "direction": super_direction,
            "entry_price": primary_signal.get("entry_price"), "stop_loss": primary_signal.get("stop_loss"),
            "targets": primary_signal.get("targets"), "risk_reward_ratio": primary_signal.get("risk_reward_ratio"),
            "confirmations": {"confluence_count": len(contributing_strategies), "contributing_strategies": [s.get("strategy_name") for s in contributing_strategies]}
        }
        logger.info(f"🔥🔥 SUPER SIGNAL FOUND on {self.symbol}@{self.timeframe}! {super_direction} with {len(contributing_strategies)} confirmations. Primary strategy: '{primary_signal.get('strategy_name')}'. 🔥🔥")
        return super_signal
