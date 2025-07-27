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

# ==========================================================
# API نهایی و هوشمند
# ==========================================================
def get_composite_signal_view(request):
    symbol = request.GET.get('symbol', 'BTC-USDT').upper()
    requested_tf = request.GET.get('timeframe') 

    try:
        fetcher = ExchangeFetcher()
        orchestrator = MasterOrchestrator()

        if requested_tf:
            df, source = _get_data_with_fallback(fetcher, symbol, requested_tf, limit=300, min_length=200)
            if df is None:
                return JsonResponse({'error': f'Not enough data for timeframe {requested_tf}.'}, status=404)
            
            single_analysis = orchestrator.analyze_single_dataframe(df, requested_tf)
            single_analysis['source'] = source
            final_result = single_analysis

        else:
            timeframes_to_analyze = ['5m', '15m', '1h', '4h', '1d']
            all_tf_analysis = {}
            for tf in timeframes_to_analyze:
                df, source = _get_data_with_fallback(fetcher, symbol, tf, limit=300, min_length=200)
                if df is not None:
                    analysis = orchestrator.analyze_single_dataframe(df, tf)
                    analysis['source'] = source
                    all_tf_analysis[tf] = analysis
            
            if not all_tf_analysis:
                return JsonResponse({'error': 'Could not fetch enough data for any timeframe.'}, status=404)

            final_result = orchestrator.get_multi_timeframe_signal(all_tf_analysis)

        return JsonResponse(convert_numpy_types(final_result), safe=False)

    except Exception as e:
        logger.error(f"Error in get_composite_signal_view: {e}\n{traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)

