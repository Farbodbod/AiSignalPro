import time
import requests
import logging
import traceback
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.http import JsonResponse

# موتورهای تحلیلی
from .exchange_fetcher import ExchangeFetcher
from engines.master_orchestrator import MasterOrchestrator
from engines.signal_adapter import SignalAdapter
from engines.trade_manager import TradeManager

logger = logging.getLogger(__name__)

EXCHANGE_FALLBACK_LIST = ['kucoin', 'mexc', 'okx', 'gateio']

def convert_numpy_types(obj):
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: convert_numpy_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(i) for i in obj]
    return obj

def _get_data_with_fallback(fetcher, symbol, interval, limit, min_length):
    for source in EXCHANGE_FALLBACK_LIST:
        logger.info(f"Attempting to fetch data from {source} for {symbol}...")
        kline_data = fetcher.get_klines(source=source, symbol=symbol, interval=interval, limit=limit)
        if kline_data and len(kline_data) >= min_length:
            logger.info(f"Successfully fetched {len(kline_data)} candles from {source}.")
            return pd.DataFrame(kline_data), source
    return None, None

def _generate_signal_object(symbol, requested_tf, strategy):
    """تابع کمکی برای تولید آبجکت سیگنال نهایی جهت جلوگیری از تکرار کد"""
    fetcher = ExchangeFetcher()
    orchestrator = MasterOrchestrator()
    
    all_tf_analysis = {}
    timeframes_to_analyze = [requested_tf] if requested_tf else ['5m', '15m', '1h', '4h', '1d']

    for tf in timeframes_to_analyze:
        limit = 300 if tf in ['1h', '4h', '1d'] else 100
        min_length = 200 if tf in ['1h', '4h', '1d'] else 50
        
        df, source = _get_data_with_fallback(fetcher, symbol, tf, limit=limit, min_length=min_length)
        if df is not None:
            analysis = orchestrator.analyze_single_dataframe(df, tf)
            analysis['source'] = source
            analysis['symbol'] = symbol
            analysis['interval'] = tf
            all_tf_analysis[tf] = analysis
    
    if not all_tf_analysis:
        return None

    if requested_tf and requested_tf in all_tf_analysis:
         final_result = all_tf_analysis[requested_tf]
    else:
        final_result = orchestrator.get_multi_timeframe_signal(all_tf_analysis)

    # --- اصلاحیه: ai_output اضافی از اینجا حذف شد ---
    adapter = SignalAdapter(
        analytics_output=final_result,
        strategy=strategy
    )
    return adapter.combine()


def get_composite_signal_view(request):
    symbol = request.GET.get('symbol', 'BTC-USDT').upper()
    requested_tf = request.GET.get('timeframe') 
    strategy = request.GET.get('strategy', 'balanced')
    try:
        final_signal_object = _generate_signal_object(symbol, requested_tf, strategy)
        if final_signal_object is None:
            return JsonResponse({'error': 'Could not fetch enough data for any requested timeframe.'}, status=404)
        return JsonResponse(convert_numpy_types(final_signal_object), safe=False)
    except Exception as e:
        logger.error(f"Error in get_composite_signal_view: {e}\n{traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)


def execute_trade_view(request):
    """آخرین سیگنال را تحلیل کرده و در صورت BUY/SELL، یک معامله باز می‌کند."""
    symbol = request.GET.get('symbol', 'BTC-USDT').upper()
    strategy = request.GET.get('strategy', 'balanced')
    try:
        final_signal_object = _generate_signal_object(symbol, None, strategy)
        if final_signal_object is None:
            return JsonResponse({'error': 'Could not generate a signal to execute.'}, status=404)

        trade_manager = TradeManager()
        new_trade = trade_manager.start_trade_from_signal(final_signal_object)

        if new_trade:
            return JsonResponse({"status": "Trade Opened", "trade_id": str(new_trade.id)})
        else:
            return JsonResponse({"status": "No Trade Opened", "signal": final_signal_object.get("signal_type")})

    except Exception as e:
        logger.error(f"Error in execute_trade_view: {e}\n{traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)


def list_open_trades_view(request):
    """لیست تمام معاملات باز را نمایش می‌دهد."""
    try:
        trade_manager = TradeManager()
        open_trades = trade_manager.get_open_trades()
        return JsonResponse(open_trades, safe=False)
    except Exception as e:
        logger.error(f"Error in list_open_trades_view: {e}\n{traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)
