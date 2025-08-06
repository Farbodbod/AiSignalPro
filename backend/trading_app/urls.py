# trading_app/urls.py (نسخه نهایی و تمیز شده)

from django.contrib import admin
from django.urls import path
from core import views  # ما فقط از فایل views استفاده می‌کنیم

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # --- این تنها آدرس API فعال و مورد نیاز ماست ---
    # این همان لینکی است که داشبورد شما در آینده از آن برای دریافت سیگنال استفاده خواهد کرد.
    path('api/get-composite-signal/', views.get_composite_signal_view, name='get-composite-signal'),

    # آدرس مربوط به system_status_view که وجود نداشت، حذف شده است.
]
