# engines/master_orchestrator.py (v25.2 - Final Production Engine)

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
    The strategic mastermind of AiSignalPro (v25.2 - Final Production Engine).
    This version consolidates all critical upgrades for absolute stability and reliability:
    1.  Robust, correctly resampled data for the Dynamic HTF Engine.
    2.  A hardened, strict, and professional-grade prompt for AI validation.
    3.  Defensive validation of all AI responses to prevent system errors.
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
        self.ENGINE_VERSION = "25.2.0"
        
        logger.info(f"MasterOrchestrator v{self.ENGINE_VERSION} (Final Production Engine) initialized.")

    def _resample_df(self, df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        """Resamples the primary dataframe to a higher timeframe for HTF analysis."""
        try:
            if df.index.tz is None:
                df.index = df.index.tz_localize('UTC')

            agg_rules = { 'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum' }
            ohlcv_df = df[['open', 'high', 'low', 'close', 'volume']]
            resampled_df = ohlcv_df.resample(timeframe).agg(agg_rules)
            resampled_df.dropna(inplace=True)
            logger.info(f"Successfully resampled {len(df)} rows to {len(resampled_df)} rows for timeframe {timeframe}.")
            return resampled_df
        except Exception as e:
            logger.error(f"Failed to resample DataFrame to {timeframe}: {e}", exc_info=True)
            return pd.DataFrame()

    def _find_super_signal(self, signals: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        min_confluence = self.config.get("general", {}).get("min_confluence_for_super_signal", 3)
        buy_signals = [s for s in signals if s['direction'] == 'BUY']
        sell_signals = [s for s in signals if s['direction'] == 'SELL']
        
        super_direction, contributing_strategies = (None, [])
        if len(buy_signals) >= min_confluence:
            super_direction, contributing_strategies = ("BUY", buy_signals)
        elif len(sell_signals) >= min_confluence:
            super_direction, contributing_strategies = ("SELL", sell_signals)
        
        if not super_direction: return None
            
        priority_list = self.config.get("strategy_priority", [])
        contributing_strategies.sort(key=lambda s: priority_list.index(s.get('strategy_name', '')) if s.get('strategy_name', '') in priority_list else 99)
        primary_signal = contributing_strategies[0]
        
        super_signal = {
            "strategy_name": "SuperSignal Confluence", "direction": super_direction,
            "entry_price": primary_signal['entry_price'], "stop_loss": primary_signal['stop_loss'],
            "targets": primary_signal['targets'], "risk_reward_ratio": primary_signal['risk_reward_ratio'],
            "confirmations": { "confluence_count": len(contributing_strategies), "contributing_strategies": [s['strategy_name'] for s in contributing_strategies] }
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
Act as a professional algorithmic trading signal validator with expertise in multi-timeframe confluence and strict JSON output. Your sole purpose is to provide a final, unbiased risk assessment.

TASK:
Analyze the provided structured JSON data for a trade signal on {symbol} ({timeframe}). Validate if a high-probability trade exists.

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
        self.last_gemini_call_time = time.time()
        ai_response = self.gemini_handler.query(prompt_template)

        if not isinstance(ai_response, dict) or not all(k in ai_response for k in ['signal', 'confidence_percent', 'explanation_fa']):
            logger.critical(f"FATAL: AI response validation failed. The response format was invalid. Response: {ai_response}")
            return None

        if ai_response.get('signal') == 'HOLD':
            logger.warning(f"AI VETOED the signal for {symbol}. System signal was {signal['direction']}. Reason: {ai_response.get('explanation_fa')}")
            return None 

        return ai_response

    def run_full_pipeline(self, df: pd.DataFrame, symbol: str, timeframe: str, previous_df: Optional[pd.DataFrame] = None) -> Tuple[Dict[str, Any], Optional[pd.DataFrame]]:
        indicators_config = self.config.get('indicators', {})
        strategies_config = self.config.get('strategies', {})
        
        analyzer = IndicatorAnalyzer(df, indicators_config, strategies_config, timeframe, previous_df)
        analyzer.calculate_all()
        primary_analysis = analyzer.get_analysis_summary()
        
        htf_analysis_cache: Dict[str, Dict] = {}
        
        valid_signals = []
        for sc in self._strategy_classes:
            strategy_name = sc.strategy_name
            strategy_config = strategies_config.get(strategy_name, {})
            
            if strategy_config.get('enabled', True):
                htf_analysis = {}
                merged_strat_config = {**sc.default_config, **strategy_config}
                
                if merged_strat_config.get('htf_confirmation_enabled'):
                    htf_map = merged_strat_config.get('htf_map', {})
                    target_htf = htf_map.get(timeframe)

                    if target_htf and target_htf != timeframe:
                        if target_htf in htf_analysis_cache:
                            htf_analysis = htf_analysis_cache[target_htf]
                        else:
                            df_for_htf = self._resample_df(analyzer.final_df, target_htf)
                            min_htf_rows = self.config.get("general", {}).get("min_rows_for_htf", 50)
                            
                            if len(df_for_htf) >= min_htf_rows:
                                logger.info(f"Dynamically running HTF analysis for {symbol} on {target_htf}...")
                                htf_analyzer = IndicatorAnalyzer(df_for_htf, indicators_config, strategies_config, target_htf)
                                htf_analyzer.calculate_all()
                                htf_analysis = htf_analyzer.get_analysis_summary()
                                htf_analysis_cache[target_htf] = htf_analysis
                            else:
                                logger.warning(f"Skipping dynamic HTF analysis for {target_htf}. Insufficient data after resampling: have {len(df_for_htf)}, need {min_htf_rows}")

                try:
                    instance = sc(primary_analysis, strategy_config, self.config, timeframe, htf_analysis=htf_analysis)
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
            result = {"status": "NEUTRAL", "message": "Signal was vetoed by AI or AI response was invalid.", "full_analysis": primary_analysis, "engine_version": self.ENGINE_VERSION}
            return result, analyzer.final_df

        final_package = {"status": "SUCCESS", "symbol": symbol, "timeframe": timeframe, "base_signal": best_signal, "ai_confirmation": ai_confirmation, "full_analysis": primary_analysis, "engine_version": self.ENGINE_VERSION}
        return final_package, analyzer.final_df

