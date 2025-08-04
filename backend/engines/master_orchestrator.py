# engines/master_orchestrator.py (نسخه نهایی 12.3 - ضد خطا و پایدار)

import logging, json, time, asyncio
import pandas as pd
from typing import Dict, Any, Optional, List

# وارد کردن تمام ماژول‌های لازم
from .config import EngineConfig
from .indicator_analyzer import IndicatorAnalyzer
from .trend_analyzer import analyze_trend
from .market_structure_analyzer import MarketStructureAnalyzer
from .strategy_engine import StrategyEngine
from .candlestick_reader import CandlestickPatternDetector
from .divergence_detector import detect_divergences
from .whale_analyzer import WhaleAnalyzer
from .gemini_handler import GeminiHandler

logger = logging.getLogger(__name__)

class MasterOrchestrator:
    def __init__(self, config: Optional[EngineConfig] = None):
        self.config = config or EngineConfig()
        self.gemini_handler = GeminiHandler()
        self.whale_analyzer = WhaleAnalyzer()
        self.last_gemini_call_time = 0
        self.ENGINE_VERSION = "12.3.0"
        logger.info(f"MasterOrchestrator v{self.ENGINE_VERSION} (Stable & Fault-Tolerant Arch) initialized.")

    def _analyze_single_dataframe(self, df: pd.DataFrame) -> Dict[str, Any]:
        analysis = {}
        try:
            df_with_indicators = IndicatorAnalyzer(df).calculate_all()
            if 'atr' in df_with_indicators and 'close' in df_with_indicators and df_with_indicators['close'].iloc[-1] > 0:
                df_with_indicators['atr_normalized'] = (df_with_indicators['atr'] / df_with_indicators['close']) * 100
            
            analysis["indicators"] = {col: df_with_indicators[col].iloc[-1] for col in df_with_indicators.columns if col not in df.columns and pd.notna(df_with_indicators[col].iloc[-1])}
            analysis["trend"] = analyze_trend(df_with_indicators, "N/A")
            analysis["market_structure"] = MarketStructureAnalyzer(df_with_indicators, self.config.market_structure_config).analyze()
            analysis["divergence"] = detect_divergences(df_with_indicators)
            analysis["patterns"] = CandlestickPatternDetector(df_with_indicators, analysis).detect_high_quality_patterns()
            
            self.whale_analyzer.update_data("5m", df_with_indicators)
            self.whale_analyzer.generate_signals()
            analysis["whale_activity"] = self.whale_analyzer.get_signals("5m")
            self.whale_analyzer.clear_signals()
        except Exception as e:
            logger.error(f"Error in _analyze_single_dataframe: {e}", exc_info=True)
            return {"error": str(e)}
        return analysis

    def _enhance_strategy_score(self, strategy: Dict, analysis: Dict) -> Dict:
        direction, bonus_points, bonus_confirmations = strategy.get("direction"), 0, []
        if any(d['type'].startswith('bullish') for d in analysis.get("divergence", {}).get('rsi', [])) and direction == "BUY":
            bonus_points += self.config.bonus_scores.bullish_divergence; bonus_confirmations.append("Bullish Divergence")
        if any(d['type'].startswith('bearish') for d in analysis.get("divergence", {}).get('rsi', [])) and direction == "SELL":
            bonus_points += self.config.bonus_scores.bearish_divergence; bonus_confirmations.append("Bearish Divergence")
        if any("Bullish" in p for p in analysis.get("patterns", [])) and direction == "BUY":
            bonus_points += self.config.bonus_scores.bullish_pattern; bonus_confirmations.append("Bullish Pattern")
        if any("Bearish" in p for p in analysis.get("patterns", [])) and direction == "SELL":
            bonus_points += self.config.bonus_scores.bearish_pattern; bonus_confirmations.append("Bearish Pattern")
        strategy['score'] += bonus_points; strategy['confirmations'].extend(bonus_confirmations)
        return strategy

    def _calculate_adaptive_threshold(self, analysis_context: Dict) -> float:
        base_threshold = self.config.min_strategy_score_threshold
        main_tf_analysis = analysis_context.get('1h', {}) or analysis_context.get('4h', {})
        if not main_tf_analysis: return base_threshold
        atr_normalized = main_tf_analysis.get('indicators', {}).get('atr_normalized', 1.0)
        if atr_normalized > 1.5: return base_threshold * 1.2
        elif atr_normalized < 0.7: return base_threshold * 0.85
        trend_signal = main_tf_analysis.get('trend', {}).get('signal', 'Neutral')
        if "Strong" in trend_signal: return base_threshold * 0.9
        elif "Ranging" in trend_signal: return base_threshold * 1.1
        return base_threshold

    async def get_final_signal(self, dataframes: Dict[str, pd.DataFrame], symbol: str) -> Dict[str, Any]:
        all_potential_strategies: List[Dict] = []
        full_analysis_details: Dict = {}
        for tf, df in dataframes.items():
            if df is None or df.empty or len(df) < 50: continue
            base_analysis = self._analyze_single_dataframe(df)
            if "error" in base_analysis: continue
            full_analysis_details[tf] = {k:v for k,v in base_analysis.items() if k != 'dataframe'}
            strategy_engine = StrategyEngine(base_analysis, self.config.strategy_config)
            strategies = strategy_engine.generate_all_valid_strategies()
            for strat in strategies:
                enhanced_strat = self._enhance_strategy_score(strat, base_analysis)
                enhanced_strat['timeframe'] = tf
                enhanced_strat['weighted_score'] = enhanced_strat.get('score', 0) * self.config.timeframe_weights.get(tf, 1.0)
                all_potential_strategies.append(enhanced_strat)
        
        # --- ✨ بخش اصلاح شده و کلیدی ---
        # قبل از هر کاری، چک می‌کنیم که آیا اصلاً استراتژی معتبری پیدا شده است یا خیر
        if not all_potential_strategies:
            return {
                "final_signal": "HOLD",
                "message": "No valid strategies found that meet the initial criteria.",
                "full_analysis_details": full_analysis_details
            }
        # --- پایان بخش اصلاح شده ---

        best_strategy = max(all_potential_strategies, key=lambda s: s['weighted_score'])
        adaptive_threshold = self._calculate_adaptive_threshold(full_analysis_details)
        
        if best_strategy['weighted_score'] < adaptive_threshold:
            return {
                "final_signal": "HOLD",
                "message": f"Best strategy score ({best_strategy['weighted_score']:.2f}) is below adaptive threshold ({adaptive_threshold:.2f}).",
                "winning_strategy": best_strategy, # استراتژی برنده را هم برمی‌گردانیم تا قابل بررسی باشد
                "full_analysis_details": full_analysis_details
            }

        final_signal_type = best_strategy.get("direction")
        gemini_confirmation = {"signal": "N/A", "confidence": 0, "explanation_fa": "AI analysis not triggered."}
        if final_signal_type != "HOLD":
            now = time.time()
            if (now - self.last_gemini_call_time) < self.config.gemini_cooldown_seconds:
                gemini_confirmation["explanation_fa"] = "AI analysis skipped due to cooldown."
            else:
                self.last_gemini_call_time = now
                prompt_context = {"winning_strategy": {k:v for k,v in best_strategy.items() if 'score' not in k}, "analysis_summary": full_analysis_details.get(best_strategy['timeframe'], {})}
                prompt = (f'Analyze this JSON data for {symbol} and provide a response ONLY in JSON format with keys "signal" (BUY/SELL/HOLD) and "explanation_fa" (concise, professional explanation in Persian).\nTechnical Data: {json.dumps(prompt_context, indent=2, default=str)}')
                gemini_confirmation = await self.gemini_handler.query(prompt)

        return {"symbol": symbol, "engine_version": self.ENGINE_VERSION, "final_signal": final_signal_type, "winning_strategy": best_strategy, "full_analysis_details": full_analysis_details, "gemini_confirmation": gemini_confirmation}

