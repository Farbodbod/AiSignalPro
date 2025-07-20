from django.contrib import admin
from .models import Signal, Trade

# Register your models here.

@admin.register(Signal)
class SignalAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'signal_type', 'timestamp', 'status')
    list_filter = ('status', 'symbol', 'timeframe')
    search_fields = ('symbol', 'signal_type')

@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'entry_price', 'status', 'pnl', 'opened_at')
    list_filter = ('status', 'symbol')
    search_fields = ('symbol',)
from django.contrib import admin

# Register your models here.
