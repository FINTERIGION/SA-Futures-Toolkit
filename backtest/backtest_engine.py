"""
回测引擎模块
负责：
  - 自定义 Analyzer（权益曲线、每日收益、持仓记录）
  - 交易日志收集与 CSV 导出
  - 回测指标计算（夏普、最大回撤、胜率、盈亏比等）
  - 运行 Cerebro 并返回结构化结果
"""

import os
import math
import datetime
import csv
import backtrader as bt
import backtrader.analyzers as btanalyzers
import pandas as pd
import numpy as np


# ==============================================================================
# 自定义 Analyzer：逐日记录权益、收益率、持仓
# ==============================================================================

class DailyEquityAnalyzer(bt.Analyzer):
    """
    每个 bar 记录：日期、账户总权益、当日持仓、当日收益率
    """

    def start(self):
        self.equity_records = []      # [(date, equity, position)]
        self._prev_equity = self.strategy.broker.getvalue()

    def next(self):
        dt = self.strategy.datas[0].datetime.date(0)
        equity = self.strategy.broker.getvalue()
        pos = self.strategy.position.size
        daily_return = (equity - self._prev_equity) / self._prev_equity if self._prev_equity else 0.0
        self.equity_records.append({
            'date': dt,
            'equity': equity,
            'position': pos,
            'daily_return': daily_return,
        })
        self._prev_equity = equity

    def get_analysis(self):
        return self.equity_records


class TradeLogAnalyzer(bt.Analyzer):
    """
    收集每笔完整交易的开仓/平仓记录
    记录字段：
      trade_id, open_date, close_date, direction,
      open_price, close_price, size,
      gross_pnl, commission, net_pnl, margin_used
    """

    def __init__(self):
        self.trades = []
        # trade.ref -> {'direction': str, 'open_price': float, 'close_price': float}
        self._trade_info = {}

    def notify_order(self, order):
        """
        Track direction and execution prices from completed orders.
        First order on a trade = open; subsequent closing order = close.
        """
        if order.status != order.Completed:
            return
        tid = order.tradeid
        if tid not in self._trade_info:
            # First order for this trade → records open direction & price
            self._trade_info[tid] = {
                'direction':   'long' if order.isbuy() else 'short',
                'open_price':  order.executed.price,
                'close_price': order.executed.price,   # placeholder
            }
        else:
            # Subsequent order (closing) → update close price
            self._trade_info[tid]['close_price'] = order.executed.price

    def notify_trade(self, trade):
        if not trade.isclosed:
            return

        tid = trade.ref
        info = self._trade_info.pop(tid, {})
        direction   = info.get('direction',   'long')
        open_price  = info.get('open_price',  trade.price)
        close_price = info.get('close_price', trade.price)

        mult   = self.strategy.p.contract_multiplier
        margin = self.strategy.p.margin_rate
        margin_used = open_price * abs(trade.barlen or 1) * mult * margin

        # Recalculate margin from entry price and size
        margin_used = round(
            open_price
            * abs(trade.size if trade.size != 0 else 1)
            * mult * margin,
            4
        )

        self.trades.append({
            'trade_id':    trade.ref,
            'open_date':   bt.num2date(trade.dtopen).date(),
            'close_date':  bt.num2date(trade.dtclose).date(),
            'direction':   direction,
            'open_price':  round(open_price, 4),
            'close_price': round(close_price, 4),
            'size':        abs(trade.barlen) if trade.barlen else 1,
            'gross_pnl':   round(trade.pnl, 4),
            'commission':  round(trade.commission, 4),
            'net_pnl':     round(trade.pnlcomm, 4),
            'margin_used': margin_used,
        })

    def get_analysis(self):
        return self.trades


# ==============================================================================
# 回测引擎主类
# ==============================================================================

class BacktestEngine:
    """
    封装 Cerebro 配置与运行，提供结构化结果输出。

    Parameters
    ----------
    strategy_class : type
        策略类（继承自 FuturesStrategyBase）
    data_feed : bt.feeds.PandasData
        已配置好的数据 Feed
    config : dict
        回测配置字典，键：
          initial_cash       初始资金（默认 100000）
          commission_rate    手续费率（默认 0.0002）
          margin_rate        保证金比例（默认 0.10）
          contract_multiplier 合约乘数（默认 20）
          trade_size         交易手数（默认 1）
          strategy_params    传入策略的额外参数 dict（可选）
          results_dir        结果保存目录（默认 backtest/results）
          strategy_name      策略名称（用于文件命名）
    """

    DEFAULT_CONFIG = {
        'initial_cash':         100_000.0,
        'commission_rate':      0.0002,
        'margin_rate':          0.10,
        'contract_multiplier':  20,
        'trade_size':           1,
        'strategy_params':      {},
        'results_dir':          os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'results'
        ),
        'strategy_name':        'strategy',
    }

    def __init__(self, strategy_class, data_feed, config: dict = None):
        self.strategy_class = strategy_class
        self.data_feed = data_feed
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
        os.makedirs(self.config['results_dir'], exist_ok=True)

    # ------------------------------------------------------------------
    # 公开方法
    # ------------------------------------------------------------------

    def run(self) -> dict:
        """
        运行回测，返回结果字典：
          cerebro, results, equity_records, trade_logs,
          metrics, log_path
        """
        cerebro = self._build_cerebro()
        print("[BacktestEngine] 开始回测...")
        results = cerebro.run()
        strat = results[0]

        equity_records = strat.analyzers.daily_equity.get_analysis()
        trade_logs     = strat.analyzers.trade_log.get_analysis()
        metrics        = self._calc_metrics(equity_records, trade_logs)

        log_path = self._save_trade_log(trade_logs)

        self._print_summary(metrics, log_path)

        return {
            'cerebro':        cerebro,
            'strat':          strat,
            'equity_records': equity_records,
            'trade_logs':     trade_logs,
            'metrics':        metrics,
            'log_path':       log_path,
        }

    # ------------------------------------------------------------------
    # 内部方法：构建 Cerebro
    # ------------------------------------------------------------------

    def _build_cerebro(self) -> bt.Cerebro:
        cfg = self.config
        cerebro = bt.Cerebro()

        # 数据
        cerebro.adddata(self.data_feed)

        # 策略参数合并
        strat_params = {
            'contract_multiplier': cfg['contract_multiplier'],
            'trade_size':          cfg['trade_size'],
            'margin_rate':         cfg['margin_rate'],
        }
        strat_params.update(cfg.get('strategy_params', {}))
        cerebro.addstrategy(self.strategy_class, **strat_params)

        # Broker
        cerebro.broker.setcash(cfg['initial_cash'])

        # 期货手续费（按成交额比例）
        comm_info = bt.CommissionInfo(
            commission=cfg['commission_rate'],
            mult=cfg['contract_multiplier'],
            margin=cfg['margin_rate'],
            commtype=bt.CommissionInfo.COMM_PERC,
            percabs=True,
        )
        cerebro.broker.addcommissioninfo(comm_info)

        # Analyzers
        cerebro.addanalyzer(DailyEquityAnalyzer,  _name='daily_equity')
        cerebro.addanalyzer(TradeLogAnalyzer,     _name='trade_log')
        cerebro.addanalyzer(btanalyzers.SharpeRatio,
                            _name='sharpe',
                            riskfreerate=0.03,
                            annualize=True,
                            timeframe=bt.TimeFrame.Days)
        cerebro.addanalyzer(btanalyzers.DrawDown,  _name='drawdown')
        cerebro.addanalyzer(btanalyzers.Returns,   _name='returns')
        cerebro.addanalyzer(btanalyzers.TradeAnalyzer, _name='trade_analyzer')

        return cerebro

    # ------------------------------------------------------------------
    # 内部方法：计算指标
    # ------------------------------------------------------------------

    def _calc_metrics(self, equity_records: list, trade_logs: list) -> dict:
        cfg = self.config
        initial_cash = cfg['initial_cash']

        if not equity_records:
            return {}

        final_equity    = equity_records[-1]['equity']
        total_return    = (final_equity - initial_cash) / initial_cash

        # 日收益率序列
        daily_returns = [r['daily_return'] for r in equity_records]
        dr_arr = np.array(daily_returns, dtype=float)

        # 夏普比率（年化，无风险利率 3%）
        risk_free_daily = 0.03 / 252
        excess = dr_arr - risk_free_daily
        sharpe = (
            excess.mean() / excess.std() * math.sqrt(252)
            if excess.std() > 1e-10 else 0.0
        )

        # 最大回撤
        equities = np.array([r['equity'] for r in equity_records], dtype=float)
        running_max = np.maximum.accumulate(equities)
        drawdowns = (running_max - equities) / running_max
        max_drawdown = float(drawdowns.max()) if len(drawdowns) > 0 else 0.0

        # 交易统计
        n_trades = len(trade_logs)
        if n_trades > 0:
            winning_trades = [t for t in trade_logs if t['net_pnl'] > 0]
            losing_trades  = [t for t in trade_logs if t['net_pnl'] < 0]
            win_rate = len(winning_trades) / n_trades

            avg_win  = (
                sum(t['net_pnl'] for t in winning_trades) / len(winning_trades)
                if winning_trades else 0.0
            )
            avg_loss = (
                abs(sum(t['net_pnl'] for t in losing_trades) / len(losing_trades))
                if losing_trades else 0.0
            )
            profit_loss_ratio = avg_win / avg_loss if avg_loss > 1e-10 else float('inf')
        else:
            win_rate = 0.0
            profit_loss_ratio = 0.0

        return {
            'initial_cash':       initial_cash,
            'final_equity':       round(final_equity, 2),
            'total_return':       round(total_return * 100, 4),   # %
            'sharpe_ratio':       round(sharpe, 4),
            'max_drawdown':       round(max_drawdown * 100, 4),   # %
            'win_rate':           round(win_rate * 100, 4),       # %
            'profit_loss_ratio':  round(profit_loss_ratio, 4),
            'n_trades':           n_trades,
            'n_winning':          len(winning_trades) if n_trades > 0 else 0,
            'n_losing':           len(losing_trades)  if n_trades > 0 else 0,
        }

    # ------------------------------------------------------------------
    # 内部方法：保存交易日志
    # ------------------------------------------------------------------

    def _save_trade_log(self, trade_logs: list) -> str:
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        name = self.config['strategy_name']
        filename = f"{name}_trades_{ts}.csv"
        filepath = os.path.join(self.config['results_dir'], filename)

        fieldnames = [
            'trade_id', 'open_date', 'close_date', 'direction',
            'open_price', 'close_price', 'size',
            'gross_pnl', 'commission', 'net_pnl', 'margin_used',
        ]

        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(trade_logs)

        print(f"[BacktestEngine] 交易日志已保存：{filepath}")
        return filepath

    # ------------------------------------------------------------------
    # 内部方法：打印摘要
    # ------------------------------------------------------------------

    @staticmethod
    def _print_summary(metrics: dict, log_path: str):
        sep = "=" * 50
        print(sep)
        print("  回测结果摘要")
        print(sep)
        print(f"  初始资金        : {metrics.get('initial_cash', 0):>12,.2f} 元")
        print(f"  最终权益        : {metrics.get('final_equity', 0):>12,.2f} 元")
        print(f"  总收益率        : {metrics.get('total_return', 0):>11.4f} %")
        print(f"  夏普比率        : {metrics.get('sharpe_ratio', 0):>12.4f}")
        print(f"  最大回撤        : {metrics.get('max_drawdown', 0):>11.4f} %")
        print(f"  胜率            : {metrics.get('win_rate', 0):>11.4f} %")
        print(f"  盈亏比          : {metrics.get('profit_loss_ratio', 0):>12.4f}")
        print(f"  总交易次数      : {metrics.get('n_trades', 0):>12}")
        print(f"  盈利次数        : {metrics.get('n_winning', 0):>12}")
        print(f"  亏损次数        : {metrics.get('n_losing', 0):>12}")
        print(sep)
        print(f"  交易日志        : {log_path}")
        print(sep)
