"""
Strategy Module
Write your custom trading strategies in this file by inheriting from
FuturesStrategyBase.

Built-in example strategies:
  - DoubleMaStrategy            Dual moving-average crossover strategy
  - RsiMeanReversionStrategy    RSI mean-reversion strategy (requires ta-lib)

Custom strategy template:
  - MyStrategy (a template you can modify directly)
"""

import backtrader as bt
import backtrader.indicators as btind


# ==============================================================================
# Base class: all futures strategies inherit from this
# ==============================================================================

class FuturesStrategyBase(bt.Strategy):
    """
    Futures strategy base class.

    Provides common helpers such as signal logging and trade logging.
    Subclasses implement the actual logic in `next()`.

    The backtest engine injects the following params via cerebro.addstrategy():
      - contract_multiplier : contract multiplier (default 20 tons/lot)
      - trade_size          : lots per trade (default 1)
      - margin_rate         : margin ratio (default 0.10)

    Subclasses can directly use:
      self.buy_signal()    open long
      self.sell_signal()   open short
      self.close_signal()  close position
    """

    params = (
        ('contract_multiplier', 20),
        ('trade_size', 1),
        ('margin_rate', 0.10),
        ('printlog', False),
    )

    def __init__(self):
        # Signal list (used by the plotting module): [(date, price, direction), ...]
        # direction: 'buy' | 'sell' | 'close'
        self.signal_log = []
        self._pending_order = None

    # ------------------------------------------------------------------
    # Lifecycle callbacks
    # ------------------------------------------------------------------

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        date = self.datas[0].datetime.date(0)

        if order.status == order.Completed:
            direction = 'buy' if order.isbuy() else 'sell'
            self.signal_log.append({
                'date': date,
                'price': order.executed.price,
                'direction': direction,
                'size': order.executed.size,
                'comm': order.executed.comm,
            })
            if self.p.printlog:
                print(
                    f"  [{date}] Filled: {'BUY' if order.isbuy() else 'SELL'} "
                    f"price={order.executed.price:.2f} "
                    f"size={order.executed.size} "
                    f"commission={order.executed.comm:.2f}"
                )
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            if self.p.printlog:
                print(f"  [{date}] Order not filled: {order.getstatusname()}")

        self._pending_order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        if self.p.printlog:
            date = self.datas[0].datetime.date(0)
            print(f"  [{date}] Trade closed: pnl={trade.pnl:.2f}  net_pnl={trade.pnlcomm:.2f}")

    # ------------------------------------------------------------------
    # Utility methods (for subclasses)
    # ------------------------------------------------------------------

    def buy_signal(self):
        """Open long at market (futures long entry)"""
        if self._pending_order is None:
            self._pending_order = self.buy(size=self.p.trade_size)

    def sell_signal(self):
        """Open short at market (futures short entry)"""
        if self._pending_order is None:
            self._pending_order = self.sell(size=self.p.trade_size)

    def close_signal(self):
        """Close the current position"""
        if self._pending_order is None:
            self._pending_order = self.close()

    def get_position_size(self) -> int:
        """Return the current net position size (positive=long, negative=short, 0=flat)"""
        return self.position.size


# ==============================================================================
# Example strategy 1: Dual moving-average crossover
# ==============================================================================

class DoubleMaStrategy(FuturesStrategyBase):
    """
    Dual moving-average trend-following strategy (example).

    Logic:
      - Fast MA crosses above slow MA -> go long
      - Fast MA crosses below slow MA -> go short
      - On a reverse signal, close first, then open new position (executes next bar)
    """

    params = (
        ('fast_period', 5),
        ('slow_period', 20),
    )

    def __init__(self):
        super().__init__()
        self.fast_ma = btind.SMA(self.data.close, period=self.p.fast_period)
        self.slow_ma = btind.SMA(self.data.close, period=self.p.slow_period)
        self.crossover = btind.CrossOver(self.fast_ma, self.slow_ma)

    def next(self):
        # Wait if there is a pending order
        if self._pending_order:
            return

        pos = self.get_position_size()

        if self.crossover > 0:          # Golden cross -> go long
            if pos < 0:
                self.close_signal()     # Close short first
            elif pos == 0:
                self.buy_signal()

        elif self.crossover < 0:        # Death cross -> go short
            if pos > 0:
                self.close_signal()     # Close long first
            elif pos == 0:
                self.sell_signal()


# ==============================================================================
# Example strategy 2: RSI mean reversion
# ==============================================================================

class RsiMeanReversionStrategy(FuturesStrategyBase):
    """
    RSI mean-reversion strategy (example).

    Logic:
      - RSI < oversold   -> oversold, go long
      - RSI > overbought -> overbought, go short
      - Close position when RSI returns to the midline (50)
    """

    params = (
        ('rsi_period', 14),
        ('oversold', 30),
        ('overbought', 70),
    )

    def __init__(self):
        super().__init__()
        self.rsi = btind.RSI(self.data.close, period=self.p.rsi_period)

    def next(self):
        if self._pending_order:
            return

        pos = self.get_position_size()
        rsi_val = self.rsi[0]

        if pos == 0:
            if rsi_val < self.p.oversold:
                self.buy_signal()
            elif rsi_val > self.p.overbought:
                self.sell_signal()
        elif pos > 0 and rsi_val > 50:
            self.close_signal()
        elif pos < 0 and rsi_val < 50:
            self.close_signal()


# ==============================================================================
# Custom strategy template (modify this directly)
# ==============================================================================

class MyStrategy(FuturesStrategyBase):
    """
    Custom strategy template.

    Usage:
      1. Define the indicators you need in __init__
      2. Implement trading logic in next()
      3. Set STRATEGY = MyStrategy in main.py

    Available methods:
      self.buy_signal()         open long
      self.sell_signal()        open short
      self.close_signal()       close position
      self.get_position_size()  current position (positive=long, negative=short)

    Available data:
      self.data.close[0]    today's close
      self.data.open[0]     today's open
      self.data.high[0]     today's high
      self.data.low[0]      today's low
      self.data.volume[0]   today's volume
    """

    params = (
        # Add strategy parameters here, e.g.:
        # ('fast', 5),
        # ('slow', 20),
    )

    def __init__(self):
        super().__init__()
        # Define indicators here, e.g.:
        # self.fast_ma = btind.SMA(self.data.close, period=self.p.fast)
        # self.slow_ma = btind.SMA(self.data.close, period=self.p.slow)
        pass

    def next(self):
        # Wait if there is a pending order
        if self._pending_order:
            return

        pos = self.get_position_size()

        # -------------------------------------------------------
        # Write your trading logic here.
        # Example: simple price momentum.
        # -------------------------------------------------------
        # if self.data.close[0] > self.data.close[-1]:  # price rose today
        #     if pos <= 0:
        #         if pos < 0:
        #             self.close_signal()
        #         else:
        #             self.buy_signal()
        # else:
        #     if pos > 0:
        #         self.close_signal()
        pass
