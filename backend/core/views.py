from django.http import JsonResponse, HttpResponse
import pandas as pd
import traceback
import os
import logging

# وارد کردن موتورهای پروژه
from .exchange_fetcher import MultiExchangeFetcher
from engines.candlestick_reader import CandlestickPatternDetector

# (بقیه import ها و ویوهای قبلی مانند system_status_view, market_overview_view و ... در اینجا قرار دارند)
# ...

# ===================================================================
# ویو جدید برای تحلیل کندل استیک
# ===================================================================
def candlestick_analysis_view(request):
    try:
        # دریافت پارامترها از درخواست GET (مثلا: /?symbol=BTC-USDT&timeframe=1h&source=kucoin)
        symbol = request.GET.get('symbol', 'BTC-USDT')
        timeframe = request.GET.get('timeframe', '1h')
        source = request.GET.get('source', 'kucoin')

        # ۱. دریافت داده‌های کندل با استفاده از موتور exchange_fetcher
        fetcher = MultiExchangeFetcher(source).get_fetcher()
        
        # چون fetcher ما OHLCV را برمی‌گرداند، باید آن را در exchange_fetcher اضافه کنیم
        # برای این مثال، فرض می‌کنیم یک متد fetch_ohlcv وجود دارد
        ohlcv_df = fetcher.fetch_ohlcv(symbol=symbol, timeframe=timeframe)

        if ohlcv_df.empty:
            return JsonResponse({'error': 'Could not fetch OHLCV data.'}, status=400)

        # ۲. ارسال داده‌ها به موتور کندل‌خوان شما
        detector = CandlestickPatternDetector(ohlcv_df)
        patterns = detector.apply_filters(min_score=1.2, min_volume_ratio=1.0)
        
        # ۳. آماده‌سازی خروجی JSON
        # تبدیل timestamp به رشته برای ارسال در JSON
        ohlcv_df_json = ohlcv_df.reset_index()
        ohlcv_df_json['timestamp'] = ohlcv_df_json['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')

        response_data = {
            'symbol': symbol,
            'timeframe': timeframe,
            'source': source,
            'ohlcv_data': ohlcv_df_json.to_dict('records'),
            'detected_patterns': patterns
        }
        return JsonResponse(response_data)

    except Exception as e:
        logger.error(f"Error in candlestick_analysis_view: {e}\n{traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)
