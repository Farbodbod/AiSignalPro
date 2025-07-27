from django.urls import path
from core import views

urlpatterns = [
    # ما فقط API نهایی و جامع را نگه می‌داریم
    path('api/get-composite-signal/', views.get_composite_signal_view, name='composite-signal'),
]
