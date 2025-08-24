# backtest/portfolio.py (v1.0 - The Quantum Financial Center)

import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, List, Optional, Tuple

from .position_sizer import PositionSizer

logger = logging.getLogger(__name__)

class Portfolio:
    """
    Manages the account state, delegates position sizing, and tracks performance.
    This class is the financial brain of the backtesting engine.
    """

    def __init__(self, initial_equity: float, risk_per_trade_percent: float, commission_pct: float):
        self.initial_equity = initial_equity
        self.risk_per_trade_percent = risk_per_trade_percent
        self.commission_pct = commission_pct

        # ✅ UPGRADE 1: Delegating to the Position Sizer Officer
        self.position_sizer = PositionSizer()

        # --- State Variables ---
        self.cash = initial_equity
        
        # ✅ UPGRADE 2: Multi-Position Handling
        self.open_positions: Dict[str, Dict[str, Any]] = {} # Key: symbol, Value: position details

        self.closed_trades: List[Dict[str, Any]] = []
        
        # ✅ UPGRADE 4: Focus on The Equity Curve
        self._equity_curve_data: List[Tuple[pd.Timestamp, float]] = [(pd.Timestamp.min, initial_equity)]

    @property
    def total_equity(self) -> float:
        return self._equity_curve_data[-1][1] if self._equity_curve_data else self.initial_equity

    def on_candle(self, timestamp: pd.Timestamp, prices: Dict[str, float]):
        """
        Updates the portfolio's market value based on the latest candle data.
        """
        market_value = 0.0
        for symbol, position in self.open_positions.items():
            current_price = prices.get(symbol)
            if current_price is not None:
                position['market_value'] = position['quantity'] * current_price
                market_value += position['market_value']
            else: # If price is missing, use last known value
                market_value += position.get('market_value', 0)

        new_total_equity = self.cash + market_value
        
        # ✅ UPGRADE 4: Record the new equity point in the curve
        if not self._equity_curve_data or self._equity_curve_data[-1][0] != timestamp:
             self._equity_curve_data.append((timestamp, new_total_equity))

    def on_signal(self, signal: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        ✅ UPGRADE 3: Defines a Clear "Signal" Contract
        Receives a signal and determines if an order should be generated.
        Expected signal keys: 'symbol', 'direction', 'entry_price', 'stop_loss'.
        """
        symbol = signal.get('symbol')
        if not symbol: return None
        
        # For v1.0, we prevent opening a new position if one already exists for the symbol
        if symbol in self.open_positions:
            logger.debug(f"Signal for {symbol} ignored. Position already open.")
            return None

        # ✅ UPGRADE 1: Use the PositionSizer to calculate quantity
        quantity = self.position_sizer.calculate_size(
            equity=self.total_equity,
            risk_per_trade_percent=self.risk_per_trade_percent,
            entry_price=signal['entry_price'],
            stop_loss_price=signal['stop_loss']
        )

        if quantity is None or quantity <= 0:
            logger.warning(f"Order for {symbol} aborted due to invalid position size ({quantity}).")
            return None
        
        # Create an Order Event for the Broker
        order = {
            'timestamp': signal.get('timestamp'),
            'symbol': symbol,
            'direction': signal['direction'],
            'quantity': quantity,
            'order_type': 'MARKET'
        }
        return order

    def on_fill(self, fill_event: Dict[str, Any]):
        """
        ✅ UPGRADE 3: Defines a Clear "Fill Event" Contract
        Updates the portfolio state after a trade is executed.
        Expected fill_event keys: 'timestamp', 'symbol', 'direction', 'quantity', 
                                    'fill_price', 'commission'.
        """
        symbol = fill_event['symbol']
        quantity = fill_event['quantity']
        fill_price = fill_event['fill_price']
        commission = fill_event['commission']
        direction_multiplier = 1 if fill_event['direction'] == 'BUY' else -1

        # Update cash
        self.cash -= (fill_price * quantity * direction_multiplier)
        self.cash -= commission

        # ✅ UPGRADE 2: Update the multi-position dictionary
        if symbol in self.open_positions: # This is a closing trade
            # Calculate PnL and log the closed trade
            opened_position = self.open_positions.pop(symbol)
            pnl = (fill_price - opened_position['entry_price']) * quantity * direction_multiplier
            self.closed_trades.append({**fill_event, 'pnl': pnl})
            logger.info(f"Closed position {symbol}. PnL: ${pnl:.2f}")
        else: # This is an opening trade
            self.open_positions[symbol] = {
                'entry_price': fill_price,
                'quantity': quantity,
                'direction': fill_event['direction'],
                'entry_time': fill_event['timestamp'],
                'market_value': quantity * fill_price
            }
            logger.info(f"Opened new position: {fill_event['direction']} {quantity:.4f} {symbol} @ ${fill_price:.5f}")


    def generate_performance_report(self, display: bool = True) -> Dict[str, Any]:
        """
        Calculates and returns final performance metrics.
        """
        equity_curve_df = pd.DataFrame(self._equity_curve_data, columns=['timestamp', 'equity']).set_index('timestamp')
        
        # --- Placeholder for detailed metric calculations ---
        total_return_pct = (self.total_equity / self.initial_equity - 1) * 100
        
        num_trades = len(self.closed_trades)
        num_wins = len([t for t in self.closed_trades if t['pnl'] > 0])
        win_rate_pct = (num_wins / num_trades) * 100 if num_trades > 0 else 0
        
        # Max Drawdown Calculation
        rolling_max = equity_curve_df['equity'].cummax()
        drawdown = (equity_curve_df['equity'] - rolling_max) / rolling_max
        max_drawdown_pct = abs(drawdown.min() * 100) if not drawdown.empty else 0

        # Sharpe Ratio (simplified, assumes daily data for annualization)
        daily_returns = equity_curve_df['equity'].pct_change().dropna()
        sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * np.sqrt(365) if not daily_returns.empty and daily_returns.std() > 0 else 0

        report = {
            "Ending Equity": f"${self.total_equity:,.2f}",
            "Total Return": f"{total_return_pct:.2f}%",
            "Total Trades": num_trades,
            "Win Rate": f"{win_rate_pct:.2f}%",
            "Max Drawdown": f"{max_drawdown_pct:.2f}%",
            "Sharpe Ratio (Annualized)": f"{sharpe_ratio:.2f}"
        }

        if display:
            logger.info("--- Backtest Performance Report ---")
            for key, value in report.items():
                logger.info(f"{key:<25}: {value}")
            logger.info("-----------------------------------")

        return report

