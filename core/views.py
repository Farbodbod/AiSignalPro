from django.http import JsonResponse

def system_status_view(request):
    data = [
        {"name": "Kucoin", "status": "online", "ping": "120ms"},
        {"name": "Gate.io", "status": "online", "ping": "180ms"},
        {"name": "Telegram", "status": "offline", "ping": "---"},
        {"name": "Coingecko", "status": "online", "ping": "OK"},
    ]
    return JsonResponse(data, safe=False)
