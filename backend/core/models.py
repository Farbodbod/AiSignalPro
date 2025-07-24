import uuid
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

class Signal(models.Model):
    class SignalStatus(models.TextChoices):
        NEW = 'new', _('New')
        VIEWED = 'viewed', _('Viewed')
        ARCHIVED = 'archived', _('Archived')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name=_("User")
    )
    symbol = models.CharField(
        max_length=20,
        db_index=True,
        verbose_name=_("Symbol")
    )
    timestamp = models.DateTimeField(
        db_index=True,
        verbose_name=_("Signal Timestamp")
    )
    timeframe = models.CharField(
        max_length=5,
        default='1h',
        verbose_name=_("Timeframe")
    )
    signal_type = models.CharField(
        max_length=100,
        verbose_name=_("Signal Type")
    )
    price_at_signal = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        verbose_name=_("Price at Signal")
    )
    details = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Analysis Details"),
        help_text=_("Stores the full JSON output from the analysis engine.")
    )
    status = models.CharField(
        max_length=10,
        choices=SignalStatus.choices,
        default=SignalStatus.NEW,
        db_index=True,
        verbose_name=_("Status")
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))

    class Meta:
        verbose_name = _("Signal")
        verbose_name_plural = _("Signals")
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.signal_type} on {self.symbol} at {self.timestamp.strftime('%Y-%m-%d %H:%M')}"


class Trade(models.Model):
    class TradeStatus(models.TextChoices):
        OPEN = 'open', _('Open')
        CLOSED = 'closed', _('Closed')
        CANCELED = 'canceled', _('Canceled')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name=_("User")
    )
    signal = models.ForeignKey(
        Signal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Associated Signal")
    )
    symbol = models.CharField(max_length=20, db_index=True, verbose_name=_("Symbol"))
    entry_price = models.DecimalField(max_digits=20, decimal_places=8, verbose_name=_("Entry Price"))
    exit_price = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True, verbose_name=_("Exit Price"))
    stop_loss = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True, verbose_name=_("Stop Loss"))
    take_profit = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True, verbose_name=_("Take Profit"))
    status = models.CharField(
        max_length=10,
        choices=TradeStatus.choices,
        default=TradeStatus.OPEN,
        db_index=True,
        verbose_name=_("Status")
    )
    pnl = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Profit/Loss ($)")
    )
    notes = models.TextField(blank=True, verbose_name=_("Notes"))
    opened_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Opened At"))
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Closed At"))

    class Meta:
        verbose_name = _("Trade")
        verbose_name_plural = _("Trades")
        ordering = ['-opened_at']

    def __str__(self):
        return f"Trade on {self.symbol} | Entry: {self.entry_price} | Status: {self.get_status_display()}"
