# core/views.py (نسخه نهایی و کامل با فرمت هوشمند)

import logging
from django.http import JsonResponse
from rest_framework.decorators import api_view
from core.models import AnalysisSnapshot

logger = logging.getLogger(__name__)

# --- این تابع قدیمی شماست و بدون تغییر باقی می‌ماند ---
@api_view(['GET'])
def get_composite_signal_view(request):
    """
    این نقطه پایانی API آخرین تحلیل ذخیره شده برای یک جفت‌ارز و تایم‌فریم مشخص را
    از دیتابیس می‌خواند.
    """
    symbol = request.GET.get('symbol', 'BTC/USDT').upper().replace('-', '/')
    timeframe = request.GET.get('timeframe', '1h')
    
    try:
        snapshot = AnalysisSnapshot.objects.filter(symbol=symbol, timeframe=timeframe).first()
        if snapshot:
            response_data = snapshot.signal_package if snapshot.status == "SUCCESS" else {
                "status": "NEUTRAL",
                "message": "Market conditions did not meet any strategy criteria at last check.",
                "full_analysis": snapshot.full_analysis
            }
            return JsonResponse(response_data, status=200, json_dumps_params={'ensure_ascii': False})
        else:
            return JsonResponse({
                "status": "NOT_FOUND",
                "message": "No analysis snapshot is available yet for this symbol/timeframe."
            }, status=404)
    except Exception as e:
        logger.critical(f"CRITICAL ERROR in get_composite_signal_view for {symbol}: {e}", exc_info=True)
        return JsonResponse({"status": "ERROR", "message": "An internal server error occurred."}, status=500)


# --- تابع جدید برای داشبورد فرماندهی (با منطق اصلاح شده) ---
@api_view(['GET'])
def get_full_dashboard_analysis(request, symbol: str):
    """
    این ویو، یک داشبورد فرماندهی کامل برای یک نماد خاص ایجاد می‌کند.
    """
    
    # ✅ SURGICAL FIX: Upgraded symbol formatting logic
    formatted_symbol = symbol.upper().replace('-', '/')
    # If no slash is present, try to intelligently add one based on common quote currencies.
    if '/' not in formatted_symbol:
        common_bases = ['USDT', 'BUSD', 'USDC', 'BTC', 'ETH', 'USD']
        for base in common_bases:
            if formatted_symbol.endswith(base):
                asset = formatted_symbol[:-len(base)]
                formatted_symbol = f"{asset}/{base}"
                break
    
    try:
        configured_timeframes = ["5m", "15m", "1h", "4h", "1d"]
        snapshots = AnalysisSnapshot.objects.filter(symbol=formatted_symbol)
        
        snapshot_map = {snap.timeframe: snap for snap in snapshots}

        dashboard_data = {}
        for tf in configured_timeframes:
            snapshot = snapshot_map.get(tf)
            
            if snapshot:
                timeframe_data = {
                    "status": snapshot.status,
                    "full_analysis": snapshot.full_analysis
                }
                if snapshot.status == "SUCCESS":
                    timeframe_data["signal_package"] = snapshot.signal_package
                dashboard_data[tf] = timeframe_data
            else:
                dashboard_data[tf] = {"status": "NOT_FOUND", "message": "Analysis pending or not yet available."}

        return JsonResponse(dashboard_data, status=200, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        logger.critical(f"CRITICAL ERROR in get_full_dashboard_analysis for {formatted_symbol}: {e}", exc_info=True)
        return JsonResponse({"status": "ERROR", "message": "An internal server error occurred."}, status=500)
