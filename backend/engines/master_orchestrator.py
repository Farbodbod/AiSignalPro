# backend/engines/master_orchestrator.py (v36.1 - Blueprint Processor Fix)

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
from engines.signal_adapter import SignalAdapter
from .telegram_handler import TelegramHandler

logger = logging.getLogger(__name__)

class MasterOrchestrator:
    """
    The strategic mastermind of AiSignalPro (v36.1 - Blueprint Processor Fix).
    -------------------------------------------------------------------------
    This version introduces a critical fix to the strategy pipeline to correctly
    process both legacy signals and modern "Trade Blueprints". It now intelligently
    detects blueprints, invokes the BaseStrategy's risk calculation engine to
    transform them into complete signals, and prepares a clean, standardized
    signal package for the AI, ensuring seamless operation for all strategy types.
    """

    def __init__(self, config: Dict[str, Any], telegram_handler: TelegramHandler):
        self.config = config
        self.telegram_handler = telegram_handler
        
        self._strategy_classes: List[Type[BaseStrategy]] = [
            TrendRiderPro, VwapMeanReversion, DivergenceSniperPro, PullbackSniperPro, RangeHunterPro, WhaleReversal,
            VolumeCatalystPro, BreakoutHunter, IchimokuHybridPro, ChandelierTrendRider,
            KeltnerMomentumBreakout, BollingerBandsDirectedMaestro, PivotConfluenceSniper, ConfluenceSniper,
            EmaCrossoverStrategy, OracleXPro,
        ]
        self.gemini_handler = GeminiHandler()
        self.news_fetcher = NewsFetcher()
        self.last_gemini_call_times: Dict[Tuple[str, str], float] = {}
        self.ENGINE_VERSION = "36.1.0" # Version updated
        logger.info(f"MasterOrchestrator v{self.ENGINE_VERSION} (Blueprint Processor Fix) initialized.")

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
                
                signal_or_blueprint = instance.check_signal()

                if signal_or_blueprint:
                    # ✅ SURGICAL FIX 1: Intelligently process both blueprints and legacy signals
                    final_signal = signal_or_blueprint
                    
                    # Check if this is a blueprint that needs processing by BaseStrategy's engine
                    if "sl_logic" in final_signal and "risk_reward_ratio" not in final_signal:
                        logger.debug(f"Blueprint from '{strategy_name}' detected. Processing risk parameters...")
                        risk_params = instance._calculate_smart_risk_management(
                            entry_price=final_signal['entry_price'],
                            direction=final_signal['direction'],
                            sl_params=final_signal.get('sl_logic'),
                            tp_logic=final_signal.get('tp_logic')
                        )
                        if risk_params:
                            final_signal.update(risk_params)
                        else:
                            logger.warning(f"Blueprint from '{strategy_name}' failed risk calculation and was discarded.")
                            continue # Skip this failed blueprint and proceed to the next strategy
                    
                    final_signal["strategy_name"] = instance.strategy_name
                    valid_signals.append(final_signal)

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
        
        best_signal = self._find_super_signal(qualified_signals, symbol, timeframe)
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
        
        if ai_confirmation is None:
            return {"status": "NEUTRAL", "message": "AI analysis failed or response was invalid.", "full_analysis": primary_analysis, "engine_version": self.ENGINE_VERSION}

        if ai_confirmation.get("signal", "").upper() == "HOLD":
            logger.warning(f"AI VETOED for {symbol}@{timeframe}. Sending notification...")
            try:
                veto_message = SignalAdapter.format_vetoed_signal_for_telegram(
                    base_signal=best_signal,
                    ai_confirmation=ai_confirmation,
                    symbol=symbol,
                    timeframe=timeframe,
                    engine_version=self.ENGINE_VERSION
                )
                await self.telegram_handler.send_message_async(veto_message)
            except Exception as e:
                logger.error(f"Failed to send VETO notification for {symbol}@{timeframe}: {e}", exc_info=True)
            
            return {"status": "NEUTRAL", "message": "Signal was vetoed by AI.", "full_analysis": primary_analysis, "engine_version": self.ENGINE_VERSION}

        return {"status": "SUCCESS", "symbol": symbol, "timeframe": timeframe, "base_signal": best_signal, "ai_confirmation": ai_confirmation, "full_analysis": primary_analysis, "engine_version": self.ENGINE_VERSION}

    def _create_ai_mission_briefing(self, analysis: Dict[str, Any], htf_context: Dict[str, Any], timeframe: str) -> Dict[str, Any]:
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
        
        # ✅ SURGICAL FIX 2: Create a clean signal for the AI, removing blueprint-specific keys.
        clean_signal_for_ai = {
            key: value for key, value in signal.items() 
            if key not in ['sl_logic', 'tp_logic']
        }
        
        market_context = self._create_ai_mission_briefing(primary_analysis, htf_context, timeframe)
        news_headlines = await self.news_fetcher.get_headlines(symbol)
        
        prompt_context = {
            "BASE_SIGNAL": clean_signal_for_ai, 
            "MARKET_CONTEXT": market_context,
            "NEWS_HEADLINES": news_headlines if news_headlines is not None else "News fetcher disabled or failed."
        }
        json_data = json.dumps(prompt_context, indent=2, ensure_ascii=False, default=str)
        
        prompt_template = f"""
Act as 'Oracle-X', a Grandmaster of Quantum Trading and a Genius Strategic Cryptocurrency Trader.

**Core Mission:** Your ultimate goal is to achieve long-term, exponential capital growth by obtaining Superior Risk-Adjusted Returns.

**Philosophy of Action:** You are a complete package. You are not just a risk manager; you are an opportunity creator. You must masterfully balance calculated aggression to exploit opportunities with iron-clad, surgical risk control to protect capital.

---
**TASK:**

Your mission is to act as the final decision-maker. You must hunt for high-probability, asymmetric opportunities where the potential reward heavily outweighs the calculated risks. Your analysis must be ruthless, objective, and stripped of all emotional bias.

To achieve this, structure your internal reasoning as follows:

1.  **THE EDGE (دلایل ورود و برتری آماری):** Clearly identify all points of confluence and technical evidence that support this trade. What is the statistical edge that makes this opportunity compelling?

2.  **THE RISKS (دلایل انصراف و نقاط ابطال):** Identify all points of divergence, conflicting signals, and potential invalidation points. What could go wrong? Where is the thesis invalidated?

3.  **THE VERDICT (جمع‌بندی نهایی و حکم):** Synthesize "The Edge" and "The Risks". Based on your core mission of achieving superior risk-adjusted returns, issue your final, decisive judgment.

---
**INPUT DATA STRUCTURE:**
You will receive a JSON object with three main keys:
1. `BASE_SIGNAL`: The primary signal generated by our rule-based strategy.
2. `MARKET_CONTEXT`: A curated summary of key indicator states across multiple timeframes.
3. `NEWS_HEADLINES`: A list of recent, relevant news headlines for sentiment analysis.

---
**RULES (THE ORACLE'S DOCTRINE):**

1.  **Doctrine of Objectivity (اصل عینیت - خروجی JSON):** Your response MUST be a single, valid JSON object and nothing else. Adhere strictly to the provided output schema below.

    ```json
    {{
      "signal": "BUY" | "SELL" | "HOLD",
      "confidence_percent": integer (0-100), // Preferred key. You may use "confidence" as a fallback if necessary.
      "opportunity_type": "Major Trend Continuation" | "Short-Term Momentum Play" | "Mean Reversion" | "High-Risk Counter-Trend" | "Uncertain",
      "confidence_drivers": ["string"],
      "explanation_fa": "string", // A professional summary in PERSIAN, strictly 2-4 sentences.
      "improvement_suggestion": "string" // Optional
    }}
    ```

2.  **Doctrine of Proportionality (اصل تناسب - بایاس تطبیقی HTF):** This is your most critical heuristic. Your judgment of higher-timeframe (HTF) conflict MUST be proportional to the signal's native timeframe.
    -   For **HIGH-TIMEFRAME signals ('1h', '4h', '1d')**, a strong HTF conflict is a near-fatal flaw. It MUST lead to a **VETO** or a confidence score **below 40%**.
    -   For **LOW-TIMEFRAME signals ('5m', '15m')**, a strong HTF conflict is a significant but not fatal consideration. You MUST **reduce confidence moderately**, but your primary focus should be on the immediate strength of the price action.

3.  **Doctrine of Asymmetry (اصل عدم تقارن - بایاس ریسک به ریوارد):** You are a hunter of asymmetric opportunities. Before considering a high R/R as a positive factor, you **MUST** first validate the soundness of the proposed `stop_loss` and `targets` against the `MARKET_CONTEXT`. **Only if the SL and TP levels are technically logical**, can you then consider an exceptional R/R (> 5.0) as a powerful confidence driver. If the R/R is high but the levels are illogical, it's a trap; treat it with extreme suspicion.

4.  **Doctrine of Primacy (اصل اولویت - اخبار تاثیرگذار):** Systemic, high-impact news is a non-negotiable override. If such news creates systemic risk that contradicts the signal, you MUST issue a **VETO**.

5.  **Doctrine of Conviction (اصل اعتقاد راسخ - ماتریس اطمینان):** Your `confidence_percent` dictates your final `signal`.
    -   **< 45%:** Always `HOLD`.
    -   **45%-65%:** `HOLD` is the default. `BUY`/`SELL` is only permissible for perfectly classified opportunities with an exceptionally strong primary driver and a good R/R.
    -   **> 65%:** `BUY`/`SELL` is authorized.

6.  **Doctrine of Realism (اصل واقع‌گرایی - بررسی سلامت):** Critically evaluate the `stop_loss` and `targets`. If they appear irrational, you MUST issue a **VETO** and use the `improvement_suggestion` field to propose a more logical risk structure.

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
            if not isinstance(ai_response, dict):
                logger.warning(f"AI response was not a dictionary. Response: {ai_response}")
                ai_response = {}

            validated_signal = str(ai_response.get("signal", "HOLD")).upper()
            if validated_signal not in ["BUY", "SELL", "HOLD"]:
                logger.warning(f"Invalid 'signal' value from AI: '{validated_signal}'. Defaulting to HOLD.")
                validated_signal = "HOLD"

            confidence_val = ai_response.get("confidence_percent")
            if confidence_val is None:
                confidence_val = ai_response.get("confidence")
            validated_confidence = int(confidence_val or 0)
            if not (0 <= validated_confidence <= 100):
                logger.warning(f"Confidence '{validated_confidence}' out of range. Clamping to 0-100.")
                validated_confidence = max(0, min(100, validated_confidence))

            explanation_fa = ai_response.get("explanation_fa", "AI response was incomplete or malformed.")
            opportunity_type = ai_response.get("opportunity_type", "Uncertain")
            confidence_drivers = ai_response.get("confidence_drivers", ["Incomplete Response"])
            improvement_suggestion = ai_response.get("improvement_suggestion", "")

            validated_response = {
                "signal": validated_signal,
                "confidence_percent": validated_confidence,
                "opportunity_type": opportunity_type,
                "confidence_drivers": confidence_drivers,
                "explanation_fa": explanation_fa,
                "improvement_suggestion": improvement_suggestion
            }
            return validated_response
            
        except Exception as e:
            logger.critical(f"FATAL: AI response could not be parsed even with safeguards. Error: {e}. Response: {ai_response}"); return None

    def _find_super_signal(self, signals: List[Dict[str, Any]], symbol: str, timeframe: str) -> Optional[Dict[str, Any]]:
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
        logger.info(f"🔥🔥 SUPER SIGNAL FOUND on {symbol}@{timeframe}! {super_direction} with {len(contributing_strategies)} confirmations. Primary strategy: '{primary_signal.get('strategy_name')}'. 🔥🔥")
        return super_signal
