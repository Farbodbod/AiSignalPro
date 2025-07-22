from django.http import JsonResponse

def system_status_view(request):
    """
    یک نمای ساده که وضعیت اتصال به سرویس‌ها را برمی‌گرداند.
    """
    data = [
      { "name": 'Kucoin', "status": 'online', "ping": '120ms' },
      { "name": 'Gate.io', "status": 'online', "ping": '180ms' },
      { "name": 'Telegram', "status": 'offline', "ping": '---' },
      { "name": 'Coingecko', "status": 'online', "ping": 'OK' },
    ]
    
    # داده‌ها را به صورت JSON به فرانت‌اند ارسال می‌کنیم
    return JsonResponse(data, safe=False)
