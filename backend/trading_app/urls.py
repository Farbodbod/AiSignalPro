# trading_app/urls.py (نسخه نهایی و کامل)

from django.contrib import admin
from django.urls import path
from core import views

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # --- API قدیمی برای دریافت سیگنال تکی (همچنان فعال) ---
    path('api/get-composite-signal/', views.get_composite_signal_view, name='get-composite-signal'),

    # --- ✅ MIRACLE UPGRADE: API جدید برای داشبورد فرماندهی کامل ---
    # این مسیر یک پارامتر ورودی به نام 'symbol' برای دریافت نام ارز می‌گیرد.
    path('api/dashboard/<str:symbol>/', views.get_full_dashboard_analysis, name='get_full_dashboard'),
]
