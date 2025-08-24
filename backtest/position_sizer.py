# backtest/position_sizer.py (v1.0 - The Risk Officer)

import logging
from typing import Optional

logger = logging.getLogger(__name__)

class PositionSizer:
    """
    A dedicated, single-responsibility class for calculating position size.
    It implements risk management models to determine the appropriate quantity
    for a trade based on the portfolio's equity and the trade's specific risk.
    """

    def calculate_size(
        self,
        equity: float,
        risk_per_trade_percent: float,
        entry_price: float,
        stop_loss_price: float
    ) -> Optional[float]:
        """
        Calculates the position size based on a fixed fractional risk model.

        Args:
            equity (float): The current total equity of the portfolio.
            risk_per_trade_percent (float): The percentage of equity to risk.
            entry_price (float): The intended entry price of the trade.
            stop_loss_price (float): The intended stop-loss price for the trade.

        Returns:
            Optional[float]: The calculated quantity of the asset to trade, or None if risk is invalid.
        """
        if entry_price is None or stop_loss_price is None:
            logger.warning("PositionSizer: Cannot calculate size with missing entry or stop-loss.")
            return None

        risk_per_unit = abs(entry_price - stop_loss_price)
        if risk_per_unit <= 1e-9: # Prevent division by zero for extremely tight stops
            logger.warning(f"PositionSizer: Risk per unit is zero or negligible. Cannot size position.")
            return None

        risk_amount_in_currency = equity * (risk_per_trade_percent / 100.0)
        position_size = risk_amount_in_currency / risk_per_unit

        logger.debug(f"Sizing calculation: Equity=${equity:.2f}, RiskAmount=${risk_amount_in_currency:.2f}, "
                     f"RiskPerUnit=${risk_per_unit:.5f} -> Size={position_size:.8f}")

        return position_size

