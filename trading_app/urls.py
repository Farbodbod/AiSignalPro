from django.contrib import admin
from django.urls import path
# We have removed the unnecessary 'home_page_view' from this import
from core.views import all_data_view, system_status_view, market_overview_view

urlpatterns = [
    # The path for the test view has been removed
    path('admin/', admin.site.urls),
    path('api/status/', system_status_view, name='system-status'),
    path('api/market-overview/', market_overview_view, name='market-overview'),
    path('api/data/all/', all_data_view, name='all-data'),
]
