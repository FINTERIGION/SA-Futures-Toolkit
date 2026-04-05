"""
策略模块
用户在此文件中编写自定义交易策略，继承 FuturesStrategyBase 即可。

内置示例策略：
  - DoubleMaStrategy   双均线金叉死叉策略
  - RsiMeanReversion   RSI均值回归策略（示例，需要 ta-lib）

用户自定义策略模板：
  - MyStrategy（模板，直接在此基础上修改）
"""

import backtrader as bt
import backtrader.indicators as btind


# ==============================================================================
# 基础类：所有期货策略均继承此类
# ==============================================================================

class FuturesStrategyBase(bt.Strategy):
    """
    期货策略基类
    提供信号记录、交易日志等通用功能，子类通过 next() 实现具体逻辑。

    回测引擎会通过 cerebro.addstrategy() 注入以下 params：
      - contract_multiplier : 合约乘数（默认 20 吨/手）
      - trade_size          : 每次交易手数（默认 1）
      - margin_rate         : 保证金比例（默认 0.10）

    子类可直接使用：
      self.buy_signal()   发出做多信号
      self.sell_signal()  发出做空信号
      self.close_signal() 平仓信号
    """

    params = (
        ('contract_multiplier', 20),
        ('trade_size', 1),
        ('margin_rate', 0.10),
        ('printlog', False),
    )

    def __init__(self):
        # 信号列表（供绘图模块使用）：[(date, price, direction), ...]
        # direction: 'buy' | 'sell' | 'close'
        self.signal_log = []
        self._pending_order = None

    # ------------------------------------------------------------------
    # 生命周期回调
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
                    f"  [{date}] 成交: {'买入' if order.isbuy() else '卖出'} "
                    f"价格={order.executed.price:.2f} "
                    f"数量={order.executed.size} "
                    f"手续费={order.executed.comm:.2f}"
                )
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            if self.p.printlog:
                print(f"  [{date}] 订单未成交: {order.getstatusname()}")

        self._pending_order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        if self.p.printlog:
            date = self.datas[0].datetime.date(0)
            print(f"  [{date}] 平仓盈亏={trade.pnl:.2f}  净盈亏={trade.pnlcomm:.2f}")

    # ------------------------------------------------------------------
    # 工具方法（子类可调用）
    # ------------------------------------------------------------------

    def buy_signal(self):
        """市价做多（期货开多仓）"""
        if self._pending_order is None:
            self._pending_order = self.buy(size=self.p.trade_size)

    def sell_signal(self):
        """市价做空（期货开空仓）"""
        if self._pending_order is None:
            self._pending_order = self.sell(size=self.p.trade_size)

    def close_signal(self):
        """平仓"""
        if self._pending_order is None:
            self._pending_order = self.close()

    def get_position_size(self) -> int:
        """返回当前净持仓手数（正=多，负=空，0=空仓）"""
        return self.position.size


# ==============================================================================
# 示例策略 1：双均线金叉死叉
# ==============================================================================

class DoubleMaStrategy(FuturesStrategyBase):
    """
    双均线趋势跟踪策略（示例）

    逻辑：
      - 快线上穿慢线 → 做多
      - 快线下穿慢线 → 做空
      - 反向信号时先平仓再开仓（次日执行）
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
        # 有未成交订单则等待
        if self._pending_order:
            return

        pos = self.get_position_size()

        if self.crossover > 0:          # 金叉 → 做多
            if pos < 0:
                self.close_signal()     # 先平空仓
            elif pos == 0:
                self.buy_signal()

        elif self.crossover < 0:        # 死叉 → 做空
            if pos > 0:
                self.close_signal()     # 先平多仓
            elif pos == 0:
                self.sell_signal()


# ==============================================================================
# 示例策略 2：RSI均值回归
# ==============================================================================

class RsiMeanReversionStrategy(FuturesStrategyBase):
    """
    RSI均值回归策略（示例）

    逻辑：
      - RSI < oversold  → 超卖，做多
      - RSI > overbought → 超买，做空
      - RSI 回到中轴 50 时平仓
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
# 用户自定义策略模板（直接在此基础上修改）
# ==============================================================================

class MyStrategy(FuturesStrategyBase):
    """
    用户自定义策略模板

    使用方法：
      1. 在 __init__ 中定义所需指标
      2. 在 next() 中实现交易逻辑
      3. 在 main.py 的 STRATEGY 变量中指定 MyStrategy

    可用方法：
      self.buy_signal()      做多
      self.sell_signal()     做空
      self.close_signal()    平仓
      self.get_position_size() 当前持仓（正=多，负=空）

    可用数据：
      self.data.close[0]     今日收盘价
      self.data.open[0]      今日开盘价
      self.data.high[0]      今日最高价
      self.data.low[0]       今日最低价
      self.data.volume[0]    今日成交量
    """

    params = (
        # 在此添加策略参数，例如：
        # ('fast', 5),
        # ('slow', 20),
    )

    def __init__(self):
        super().__init__()
        # 在此定义指标，例如：
        # self.fast_ma = btind.SMA(self.data.close, period=self.p.fast)
        # self.slow_ma = btind.SMA(self.data.close, period=self.p.slow)
        pass

    def next(self):
        # 有未成交订单则等待
        if self._pending_order:
            return

        pos = self.get_position_size()

        # -------------------------------------------------------
        # 在此编写你的交易逻辑
        # 示例：简单价格动量
        # -------------------------------------------------------
        # if self.data.close[0] > self.data.close[-1]:  # 今日涨
        #     if pos <= 0:
        #         if pos < 0:
        #             self.close_signal()
        #         else:
        #             self.buy_signal()
        # else:
        #     if pos > 0:
        #         self.close_signal()
        pass
