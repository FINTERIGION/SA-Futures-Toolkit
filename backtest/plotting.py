"""
图表绘制模块
使用 matplotlib 绘制以下图表并保存：
  1. 资金曲线图  - 账户权益随时间变化
  2. 收益曲线图  - 累计收益率与每日收益率
  3. 持仓状态图  - 多空持仓数量变化
  4. 价格与信号图 - 收盘价走势及买卖信号标记
"""

import os
import datetime
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')   # 无显示器环境下使用非交互后端
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.gridspec import GridSpec


# 全局绘图样式
plt.rcParams.update({
    'font.sans-serif': ['DejaVu Sans', 'SimHei', 'Arial Unicode MS'],
    'axes.unicode_minus': False,
    'figure.facecolor': '#0d1117',
    'axes.facecolor':   '#161b22',
    'axes.edgecolor':   '#30363d',
    'axes.labelcolor':  '#c9d1d9',
    'xtick.color':      '#8b949e',
    'ytick.color':      '#8b949e',
    'grid.color':       '#21262d',
    'text.color':       '#c9d1d9',
    'legend.facecolor': '#161b22',
    'legend.edgecolor': '#30363d',
})

COLOR_UP    = '#3fb950'   # 绿色（盈利 / 多仓）
COLOR_DOWN  = '#f85149'   # 红色（亏损 / 空仓）
COLOR_FLAT  = '#8b949e'   # 灰色（空仓）
COLOR_PRICE = '#58a6ff'   # 蓝色（价格线）
COLOR_EQ    = '#d2a8ff'   # 紫色（权益线）


class BacktestPlotter:
    """
    回测图表生成器

    Parameters
    ----------
    equity_records : list of dict
        DailyEquityAnalyzer 的输出，字段：date, equity, position, daily_return
    trade_logs : list of dict
        TradeLogAnalyzer 的输出，字段：open_date, close_date, direction, ...
    price_df : pd.DataFrame
        原始价格 DataFrame（index=date，含 close 列），用于价格+信号图
    signal_log : list of dict
        策略的 signal_log，字段：date, price, direction（'buy'|'sell'|'close'）
    metrics : dict
        回测指标字典
    config : dict
        回测配置（含 results_dir, strategy_name 等）
    """

    def __init__(
        self,
        equity_records: list,
        trade_logs:     list,
        price_df:       pd.DataFrame,
        signal_log:     list,
        metrics:        dict,
        config:         dict,
    ):
        self.equity_records = equity_records
        self.trade_logs     = trade_logs
        self.price_df       = price_df.copy()
        self.signal_log     = signal_log
        self.metrics        = metrics
        self.config         = config

        self._results_dir   = config.get('results_dir', 'backtest/results')
        self._strategy_name = config.get('strategy_name', 'strategy')
        self._ts            = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

        os.makedirs(self._results_dir, exist_ok=True)

        # 构建 DataFrame
        self._equity_df  = pd.DataFrame(equity_records)
        if not self._equity_df.empty:
            self._equity_df['date'] = pd.to_datetime(self._equity_df['date'])
            self._equity_df.set_index('date', inplace=True)
            self._equity_df['cum_return'] = (
                self._equity_df['equity'] / self._equity_df['equity'].iloc[0] - 1
            ) * 100

    # ------------------------------------------------------------------
    # 公开方法
    # ------------------------------------------------------------------

    def plot_all(self) -> dict:
        """
        绘制全部图表，返回各图路径字典
        {
          'equity':   str,
          'returns':  str,
          'position': str,
          'signals':  str,
          'summary':  str,   # 四图合一总览
        }
        """
        paths = {}
        paths['equity']   = self._plot_equity_curve()
        paths['returns']  = self._plot_return_curve()
        paths['position'] = self._plot_position()
        paths['signals']  = self._plot_price_signals()
        paths['summary']  = self._plot_summary()
        return paths

    # ------------------------------------------------------------------
    # 图 1：资金曲线
    # ------------------------------------------------------------------

    def _plot_equity_curve(self) -> str:
        fig, ax = plt.subplots(figsize=(12, 5))
        df = self._equity_df

        ax.plot(df.index, df['equity'], color=COLOR_EQ, linewidth=1.5, label='Equity')

        # 填充回撤区域
        running_max = df['equity'].cummax()
        ax.fill_between(df.index, df['equity'], running_max,
                        where=(df['equity'] < running_max),
                        alpha=0.3, color=COLOR_DOWN, label='Drawdown')

        ax.set_title(f'{self._strategy_name} - Equity Curve', fontsize=13)
        ax.set_xlabel('Date')
        ax.set_ylabel('Equity (CNY)')
        ax.legend(loc='upper left')
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        fig.autofmt_xdate()
        ax.grid(True, alpha=0.3)

        # 标注最终指标
        m = self.metrics
        info = (
            f"Total Return: {m.get('total_return', 0):.2f}%  "
            f"Max Drawdown: {m.get('max_drawdown', 0):.2f}%  "
            f"Sharpe: {m.get('sharpe_ratio', 0):.3f}"
        )
        ax.set_xlabel(info, fontsize=9, color='#8b949e')

        path = os.path.join(
            self._results_dir,
            f"{self._strategy_name}_equity_{self._ts}.png"
        )
        fig.tight_layout()
        fig.savefig(path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f"[Plotter] 资金曲线图已保存：{path}")
        return path

    # ------------------------------------------------------------------
    # 图 2：收益曲线
    # ------------------------------------------------------------------

    def _plot_return_curve(self) -> str:
        fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
        df = self._equity_df

        # 上：累计收益率
        ax1 = axes[0]
        ax1.plot(df.index, df['cum_return'], color=COLOR_EQ, linewidth=1.5)
        ax1.fill_between(df.index, df['cum_return'], 0,
                         where=(df['cum_return'] >= 0), alpha=0.2, color=COLOR_UP)
        ax1.fill_between(df.index, df['cum_return'], 0,
                         where=(df['cum_return'] < 0), alpha=0.2, color=COLOR_DOWN)
        ax1.axhline(0, color='#8b949e', linewidth=0.8, linestyle='--')
        ax1.set_title(f'{self._strategy_name} - Return Curve', fontsize=13)
        ax1.set_ylabel('Cumulative Return (%)')
        ax1.grid(True, alpha=0.3)

        # 下：每日收益率（柱状图）
        ax2 = axes[1]
        colors = [COLOR_UP if v >= 0 else COLOR_DOWN for v in df['daily_return'] * 100]
        ax2.bar(df.index, df['daily_return'] * 100, color=colors, alpha=0.7, width=1)
        ax2.axhline(0, color='#8b949e', linewidth=0.8, linestyle='--')
        ax2.set_ylabel('Daily Return (%)')
        ax2.set_xlabel('Date')
        ax2.grid(True, alpha=0.3)

        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        fig.autofmt_xdate()

        path = os.path.join(
            self._results_dir,
            f"{self._strategy_name}_returns_{self._ts}.png"
        )
        fig.tight_layout()
        fig.savefig(path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f"[Plotter] 收益曲线图已保存：{path}")
        return path

    # ------------------------------------------------------------------
    # 图 3：持仓状态
    # ------------------------------------------------------------------

    def _plot_position(self) -> str:
        fig, ax = plt.subplots(figsize=(12, 4))
        df = self._equity_df

        pos = df['position']
        long_mask  = pos > 0
        short_mask = pos < 0
        flat_mask  = pos == 0

        ax.fill_between(df.index, pos, 0, where=long_mask,
                        alpha=0.5, color=COLOR_UP, label='Long')
        ax.fill_between(df.index, pos, 0, where=short_mask,
                        alpha=0.5, color=COLOR_DOWN, label='Short')
        ax.step(df.index, pos, color='#c9d1d9', linewidth=0.8, where='post')
        ax.axhline(0, color='#8b949e', linewidth=0.8, linestyle='--')

        ax.set_title(f'{self._strategy_name} - Position', fontsize=13)
        ax.set_ylabel('Position (Lots)')
        ax.set_xlabel('Date')
        ax.legend(loc='upper left')
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        fig.autofmt_xdate()
        ax.grid(True, alpha=0.3)

        path = os.path.join(
            self._results_dir,
            f"{self._strategy_name}_position_{self._ts}.png"
        )
        fig.tight_layout()
        fig.savefig(path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f"[Plotter] 持仓状态图已保存：{path}")
        return path

    # ------------------------------------------------------------------
    # 图 4：价格 + 信号
    # ------------------------------------------------------------------

    def _plot_price_signals(self) -> str:
        fig, ax = plt.subplots(figsize=(14, 6))

        price_df = self.price_df
        if 'close' not in price_df.columns:
            ax.text(0.5, 0.5, 'No price data', transform=ax.transAxes,
                    ha='center', va='center')
        else:
            price_df.index = pd.to_datetime(price_df.index)
            ax.plot(price_df.index, price_df['close'],
                    color=COLOR_PRICE, linewidth=1.2, label='Close', zorder=2)

            # 信号标记
            for sig in self.signal_log:
                sig_date = pd.to_datetime(sig['date'])
                sig_price = sig['price']
                direction = sig['direction']

                if direction == 'buy':
                    ax.scatter(sig_date, sig_price, marker='^', color=COLOR_UP,
                               s=80, zorder=5, label='_nolegend_')
                elif direction == 'sell':
                    ax.scatter(sig_date, sig_price, marker='v', color=COLOR_DOWN,
                               s=80, zorder=5, label='_nolegend_')

            # 图例代理
            from matplotlib.lines import Line2D
            legend_elements = [
                Line2D([0], [0], color=COLOR_PRICE, linewidth=1.5, label='Close'),
                plt.scatter([], [], marker='^', color=COLOR_UP,  s=60, label='Long Signal'),
                plt.scatter([], [], marker='v', color=COLOR_DOWN, s=60, label='Short Signal'),
            ]
            ax.legend(handles=legend_elements, loc='upper left')

        ax.set_title(f'{self._strategy_name} - Price and Trading Signals', fontsize=13)
        ax.set_ylabel('Price (CNY/ton)')
        ax.set_xlabel('Date')
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        fig.autofmt_xdate()
        ax.grid(True, alpha=0.3)

        path = os.path.join(
            self._results_dir,
            f"{self._strategy_name}_signals_{self._ts}.png"
        )
        fig.tight_layout()
        fig.savefig(path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f"[Plotter] 价格信号图已保存：{path}")
        return path

    # ------------------------------------------------------------------
    # 图 5：四图合一总览
    # ------------------------------------------------------------------

    def _plot_summary(self) -> str:
        fig = plt.figure(figsize=(16, 12))
        fig.suptitle(
            f'{self._strategy_name}  Backtest Summary\n'
            f'Return: {self.metrics.get("total_return", 0):.2f}%  '
            f'Sharpe: {self.metrics.get("sharpe_ratio", 0):.3f}  '
            f'MaxDD: {self.metrics.get("max_drawdown", 0):.2f}%  '
            f'WinRate: {self.metrics.get("win_rate", 0):.2f}%  '
            f'P/L Ratio: {self.metrics.get("profit_loss_ratio", 0):.3f}  '
            f'Trades: {self.metrics.get("n_trades", 0)}',
            fontsize=11, color='#c9d1d9', y=0.98
        )

        gs = GridSpec(3, 2, figure=fig, hspace=0.45, wspace=0.3)

        df = self._equity_df

        # 1. 资金曲线
        ax1 = fig.add_subplot(gs[0, :])
        ax1.plot(df.index, df['equity'], color=COLOR_EQ, linewidth=1.5, label='Equity')
        running_max = df['equity'].cummax()
        ax1.fill_between(df.index, df['equity'], running_max,
                         where=(df['equity'] < running_max),
                         alpha=0.3, color=COLOR_DOWN, label='Drawdown')
        ax1.set_title('Equity Curve', fontsize=10)
        ax1.set_ylabel('Equity (CNY)')
        ax1.legend(loc='upper left', fontsize=8)
        ax1.grid(True, alpha=0.3)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        plt.setp(ax1.get_xticklabels(), rotation=30, ha='right')

        # 2. 累计收益率
        ax2 = fig.add_subplot(gs[1, 0])
        ax2.plot(df.index, df['cum_return'], color=COLOR_EQ, linewidth=1.2)
        ax2.fill_between(df.index, df['cum_return'], 0,
                         where=(df['cum_return'] >= 0), alpha=0.2, color=COLOR_UP)
        ax2.fill_between(df.index, df['cum_return'], 0,
                         where=(df['cum_return'] < 0), alpha=0.2, color=COLOR_DOWN)
        ax2.axhline(0, color='#8b949e', linewidth=0.8, linestyle='--')
        ax2.set_title('Cum. Return', fontsize=10)
        ax2.set_ylabel('%')
        ax2.grid(True, alpha=0.3)
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
        plt.setp(ax2.get_xticklabels(), rotation=30, ha='right')

        # 3. 每日收益率
        ax3 = fig.add_subplot(gs[1, 1])
        colors = [COLOR_UP if v >= 0 else COLOR_DOWN for v in df['daily_return'] * 100]
        ax3.bar(df.index, df['daily_return'] * 100, color=colors, alpha=0.7, width=1)
        ax3.axhline(0, color='#8b949e', linewidth=0.8, linestyle='--')
        ax3.set_title('Daily Return', fontsize=10)
        ax3.set_ylabel('%')
        ax3.grid(True, alpha=0.3)
        ax3.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax3.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
        plt.setp(ax3.get_xticklabels(), rotation=30, ha='right')

        # 4. 持仓状态
        ax4 = fig.add_subplot(gs[2, 0])
        pos = df['position']
        ax4.fill_between(df.index, pos, 0, where=(pos > 0), alpha=0.5, color=COLOR_UP, label='Long')
        ax4.fill_between(df.index, pos, 0, where=(pos < 0), alpha=0.5, color=COLOR_DOWN, label='Short')
        ax4.step(df.index, pos, color='#c9d1d9', linewidth=0.7, where='post')
        ax4.axhline(0, color='#8b949e', linewidth=0.8, linestyle='--')
        ax4.set_title('Position', fontsize=10)
        ax4.set_ylabel('Lots')
        ax4.legend(loc='upper left', fontsize=8)
        ax4.grid(True, alpha=0.3)
        ax4.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax4.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
        plt.setp(ax4.get_xticklabels(), rotation=30, ha='right')

        # 5. 价格 + 信号
        ax5 = fig.add_subplot(gs[2, 1])
        price_df = self.price_df
        if 'close' in price_df.columns:
            price_df.index = pd.to_datetime(price_df.index)
            ax5.plot(price_df.index, price_df['close'],
                     color=COLOR_PRICE, linewidth=1.0, label='Close')
            for sig in self.signal_log:
                sig_date  = pd.to_datetime(sig['date'])
                sig_price = sig['price']
                direction = sig['direction']
                if direction == 'buy':
                    ax5.scatter(sig_date, sig_price, marker='^', color=COLOR_UP, s=40, zorder=5)
                elif direction == 'sell':
                    ax5.scatter(sig_date, sig_price, marker='v', color=COLOR_DOWN, s=40, zorder=5)
        ax5.set_title('Price & Signals', fontsize=10)
        ax5.set_ylabel('Price')
        ax5.grid(True, alpha=0.3)
        ax5.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax5.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
        plt.setp(ax5.get_xticklabels(), rotation=30, ha='right')

        path = os.path.join(
            self._results_dir,
            f"{self._strategy_name}_summary_{self._ts}.png"
        )
        fig.savefig(path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f"[Plotter] 总览图已保存：{path}")
        return path
