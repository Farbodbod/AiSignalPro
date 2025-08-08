import logging
from django.http import JsonResponse
from rest_framework.decorators import api_view
from core.models import AnalysisSnapshot # ✨ ۱. ایمپورت مدل جدید

logger = logging.getLogger(__name__)

@api_view(['GET'])
def get_composite_signal_view(request):
    """
    ✨ UPGRADE v19.0 - World-Class Architecture ✨
    این نقطه پایانی API دیگر تحلیل زنده انجام نمی‌دهد.
    این متد آخرین تحلیل ذخیره شده توسط ورکر را از دیتابیس می‌خواند.
    این روش فوق‌العاده سریع، بهینه و مقیاس‌پذیر است.
    """
    symbol = request.GET.get('symbol', 'BTC/USDT')
    timeframe = request.GET.get('timeframe', '1h')
    
    try:
        # ✨ ۲. کوئری ساده و سریع به دیتابیس
        # ما به دنبال آخرین رکورد برای جفت‌ارز و تایم‌فریم مشخص شده می‌گردیم.
        snapshot = AnalysisSnapshot.objects.filter(symbol=symbol, timeframe=timeframe).first()

        # ۳. بررسی نتیجه کوئری
        if snapshot:
            # اگر رکوردی پیدا شد
            if snapshot.status == "SUCCESS":
                # اگر وضعیت موفقیت‌آمیز بود، پکیج کامل سیگنال را برمی‌گردانیم
                # این پکیج شامل full_analysis نیز هست
                return JsonResponse(snapshot.signal_package, status=200)
            else: # اگر وضعیت NEUTRAL بود
                # یک پاسخ خنثی به همراه تحلیل کامل برمی‌گردانیم
                return JsonResponse({
                    "status": "NEUTRAL",
                    "message": "Market conditions did not meet any strategy criteria at last check.",
                    "full_analysis": snapshot.full_analysis
                }, status=200)
        else:
            # اگر هنوز هیچ رکوردی توسط ورکر برای این جفت‌ارز ذخیره نشده باشد
            return JsonResponse({
                "status": "NOT_FOUND",
                "message": "No analysis snapshot is available yet for this symbol/timeframe. Please wait for the next worker cycle."
            }, status=404)

    except Exception as e:
        logger.critical(f"CRITICAL ERROR in get_composite_signal_view for {symbol}: {e}", exc_info=True)
        return JsonResponse({"status": "ERROR", "message": "An internal server error occurred."}, status=500)
