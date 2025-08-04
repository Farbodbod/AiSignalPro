# engines/master_orchestrator.py (نسخه نهایی 12.6 - اصلاحیه قطعی قیمت)

# ... (تمام import ها و __init__ از پاسخ‌های قبلی صحیح است) ...
# ...
class MasterOrchestrator:
    def __init__(self, config: Optional[EngineConfig] = None):
        self.config = config or EngineConfig()
        self.gemini_handler = GeminiHandler()
        self.whale_analyzer = WhaleAnalyzer()
        self.last_gemini_call_time = 0
        self.ENGINE_VERSION = "12.6.0"
        logger.info(f"MasterOrchestrator v{self.ENGINE_VERSION} (Definitive Price Hotfix) initialized.")
    
    def _analyze_single_dataframe(self, df: pd.DataFrame) -> Dict[str, Any]:
        analysis = {}
        try:
            df_with_indicators = IndicatorAnalyzer(df).calculate_all()
            
            # --- ✨ اصلاحیه قطعی و نهایی برای رفع باگ اعداد منفی ✨ ---
            last_row = df_with_indicators.iloc[-1]
            
            ohlcv_cols = ['open', 'high', 'low', 'close', 'volume']
            indicators_dict = {col: last_row[col] for col in ohlcv_cols if col in last_row and pd.notna(last_row[col])}

            indicator_cols = [col for col in df_with_indicators.columns if col not in df.columns]
            for col in indicator_cols:
                if col in last_row and pd.notna(last_row[col]):
                    indicators_dict[col] = last_row[col]
            
            if 'atr' in indicators_dict and 'close' in indicators_dict and indicators_dict['close'] > 0:
                indicators_dict['atr_normalized'] = (indicators_dict['atr'] / indicators_dict['close']) * 100
            
            analysis["indicators"] = indicators_dict
            # --- پایان اصلاحیه ---

            analysis["trend"] = analyze_trend(df_with_indicators, "N/A")
            analysis["market_structure"] = MarketStructureAnalyzer(df_with_indicators, self.config.market_structure_config).analyze()
            analysis["divergence"] = detect_divergences(df_with_indicators)
            analysis["patterns"] = CandlestickPatternDetector(df_with_indicators, analysis).detect_high_quality_patterns()
            
            self.whale_analyzer.update_data("5m", df_with_indicators)
            self.whale_analyzer.generate_signals()
            analysis["whale_activity"] = self.whale_analyzer.get_signals("5m")
            self.whale_analyzer.clear_signals()
        except Exception as e:
            return {"error": str(e)}
        return analysis

    # ... (بقیه متدهای کلاس: _enhance_strategy_score, _calculate_adaptive_threshold, get_final_signal) ...
    # این متدها از پاسخ قبلی کاملاً صحیح و بدون تغییر هستند. برای کامل بودن، آنها را اینجا قرار می‌دهم.
    def _enhance_strategy_score(self, strategy: Dict, analysis: Dict, higher_tf_trend: Optional[str]) -> Dict:
        direction, bonus_points, bonus_confirmations = strategy.get("direction"), 0, []
        if any(d['type'].startswith('bullish') for d in analysis.get("divergence", {}).get('rsi', [])) and direction == "BUY":
            bonus_points += self.config.bonus_scores.bullish_divergence; bonus_confirmations.append("Bullish Divergence")
        if any(d['type'].startswith('bearish') for d in analysis.get("divergence", {}).get('rsi', [])) and direction == "SELL":
            bonus_points += self.config.bonus_scores.bearish_divergence; bonus_confirmations.append("Bearish Divergence")
        if any("Bullish" in p for p in analysis.get("patterns", [])) and direction == "BUY":
            bonus_points += self.config.bonus_scores.bullish_pattern; bonus_confirmations.append("Bullish Pattern")
        if any("Bearish" in p for p in analysis.get("patterns", [])) and direction == "SELL":
            bonus_points += self.config.bonus_scores.bearish_pattern; bonus_confirmations.append("Bearish Pattern")
        if higher_tf_trend:
            is_aligned = (direction == "BUY" and "Downtrend" not in higher_tf_trend) or (direction == "SELL" and "Uptrend" not in higher_tf_trend)
            is_conflicting = (direction == "BUY" and "Downtrend" in higher_tf_trend) or (direction == "SELL" and "Uptrend" in higher_tf_trend)
            if is_aligned: bonus_points += 5.0; bonus_confirmations.append("HTF Trend Aligned")
            elif is_conflicting: bonus_points -= 8.0; bonus_confirmations.append("HTF Trend Conflict!")
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
        timeframe_order = ['5m', '15m', '1h', '4h', '1d']
        for tf in dataframes.keys():
            base_analysis = self._analyze_single_dataframe(dataframes[tf])
            if "error" in base_analysis: continue
            full_analysis_details[tf] = {k:v for k,v in base_analysis.items() if k != 'dataframe'}
        for tf, analysis in full_analysis_details.items():
            current_tf_index = timeframe_order.index(tf) if tf in timeframe_order else -1
            higher_tf_trend = None
            if current_tf_index != -1 and current_tf_index < len(timeframe_order) - 1:
                higher_tf = timeframe_order[current_tf_index + 1]
                if higher_tf in full_analysis_details: higher_tf_trend = full_analysis_details[higher_tf].get("trend", {}).get("signal")
            strategy_engine = StrategyEngine(analysis, self.config.strategy_config)
            strategies = strategy_engine.generate_all_valid_strategies()
            for strat in strategies:
                enhanced_strat = self._enhance_strategy_score(strat, analysis, higher_tf_trend)
                enhanced_strat['timeframe'] = tf
                enhanced_strat['weighted_score'] = enhanced_strat.get('score', 0) * self.config.timeframe_weights.get(tf, 1.0)
                all_potential_strategies.append(enhanced_strat)
        if not all_potential_strategies: return {"final_signal": "HOLD", "message": "No valid strategies found."}
        best_strategy = max(all_potential_strategies, key=lambda s: s['weighted_score'])
        adaptive_threshold = self._calculate_adaptive_threshold(full_analysis_details)
        if best_strategy['weighted_score'] < adaptive_threshold:
            return {"final_signal": "HOLD", "message": f"Best score ({best_strategy['weighted_score']:.2f}) below threshold ({adaptive_threshold:.2f})."}
        final_signal_type = best_strategy.get("direction")
        gemini_confirmation = {"signal": "N/A", "confidence": 0, "explanation_fa": "AI analysis not triggered."}
        if final_signal_type != "HOLD":
            now = time.time()
            if (now - self.last_gemini_call_time) < self.config.gemini_cooldown_seconds:
                gemini_confirmation["explanation_fa"] = "AI analysis skipped due to cooldown."
            else:
                self.last_gemini_call_time = now
                prompt_context = {"winning_strategy": {k:v for k,v in best_strategy.items() if 'score' not in k}, "analysis_summary": full_analysis_details.get(best_strategy['timeframe'], {})}
                prompt = (f'Analyze JSON for {symbol} and respond ONLY in JSON with "signal" (BUY/SELL/HOLD) and "explanation_fa" (concise, Persian explanation).\nData: {json.dumps(prompt_context, indent=2, default=str)}')
                gemini_confirmation = await self.gemini_handler.query(prompt)
        return {"symbol": symbol, "engine_version": self.ENGINE_VERSION, "final_signal": final_signal_type, "winning_strategy": best_strategy, "full_analysis_details": full_analysis_details, "gemini_confirmation": gemini_confirmation}
