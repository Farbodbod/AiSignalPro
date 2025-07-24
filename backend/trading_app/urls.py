from django.contrib import admin
from django.urls import path
from core.views import (
    system_status_view, 
    market_overview_view, 
    all_data_view
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/status/', system_status_view),
    path('api/market-overview/', market_overview_view),
    path('api/data/all/', all_data_view),
]
