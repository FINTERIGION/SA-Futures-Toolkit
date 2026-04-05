"""
回测主程序模块
=============
使用方法：
  1. 修改下方 "回测参数配置" 区域的参数
  2. 将 STRATEGY 改为你想运行的策略类
  3. 运行：python backtest/main.py

目录结构：
  backtest/
    main.py          ← 本文件（回测入口，在此修改参数）
    strategy.py      ← 策略模块（在此编写交易逻辑）
    data_manager.py  ← 数据管理模块
    backtest_engine.py ← 回测引擎与指标计算
    plotting.py      ← 图表绘制模块
    results/         ← 回测结果保存目录（自动创建）
"""

import os
import sys

# 确保项目根目录在路径中（导入 update.py 等）
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_manager   import DataManager
from backtest_engine import BacktestEngine
from plotting       import BacktestPlotter

# 导入策略（修改此处选择不同策略）
from strategy import (
    DoubleMaStrategy,
    RsiMeanReversionStrategy,
    MyStrategy,
)


# ==============================================================================
# ★ 回测参数配置区（用户在此修改）
# ==============================================================================

# --- 策略选择 ---
STRATEGY = DoubleMaStrategy          # 替换为你的策略类，如 MyStrategy

# --- 策略专属参数（与策略 params 对应，留空则使用策略默认值）---
STRATEGY_PARAMS = {
    'fast_period': 5,
    'slow_period': 20,
    # 'rsi_period': 14,              # RsiMeanReversionStrategy 专属参数示例
}

# --- 回测区间 ---
START_DATE = '2020-01-01'            # 开始日期 'YYYY-MM-DD'
END_DATE   = '2024-12-31'            # 结束日期 'YYYY-MM-DD'

# --- 资金与交易参数 ---
INITIAL_CASH         = 100_000.0     # 初始资金（元）
COMMISSION_RATE      = 0.0002        # 手续费率（万分之2）
MARGIN_RATE          = 0.15          # 保证金比例（15%）
CONTRACT_MULTIPLIER  = 20            # 合约乘数（吨/手）
TRADE_SIZE           = 1             # 每次交易手数

# --- 数据更新 ---
UPDATE_DATA = True                   # True = 重新从交易所下载数据

# --- 策略名称（用于文件命名，不同策略建议填不同名称）---
STRATEGY_NAME = 'DoubleMA'

# --- 结果保存目录 ---
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')

# ==============================================================================
# 主程序（通常不需要修改以下内容）
# ==============================================================================

def main():
    print("=" * 60)
    print(f"  SA 期货回测框架")
    print(f"  策略：{STRATEGY.__name__}  [{START_DATE} → {END_DATE}]")
    print("=" * 60)

    # 1. 加载数据
    print("\n[1/4] 加载数据...")
    dm = DataManager(symbol='SA', update=UPDATE_DATA)
    data_feed = dm.get_bt_feed(start_date=START_DATE, end_date=END_DATE)
    price_df  = dm.load_dataframe(start_date=START_DATE, end_date=END_DATE)

    # 2. 配置回测引擎
    print("[2/4] 配置回测引擎...")
    config = {
        'initial_cash':        INITIAL_CASH,
        'commission_rate':     COMMISSION_RATE,
        'margin_rate':         MARGIN_RATE,
        'contract_multiplier': CONTRACT_MULTIPLIER,
        'trade_size':          TRADE_SIZE,
        'strategy_params':     STRATEGY_PARAMS,
        'results_dir':         RESULTS_DIR,
        'strategy_name':       STRATEGY_NAME,
    }
    engine = BacktestEngine(STRATEGY, data_feed, config)

    # 3. 运行回测
    print("[3/4] 运行回测...\n")
    result = engine.run()

    # 4. 绘制图表
    print("\n[4/4] 绘制图表...")
    signal_log = result['strat'].signal_log
    plotter = BacktestPlotter(
        equity_records = result['equity_records'],
        trade_logs     = result['trade_logs'],
        price_df       = price_df,
        signal_log     = signal_log,
        metrics        = result['metrics'],
        config         = config,
    )
    chart_paths = plotter.plot_all()

    # 5. 最终汇总输出
    print("\n" + "=" * 60)
    print("  图表文件路径")
    print("=" * 60)
    labels = {
        'equity':   '资金曲线图',
        'returns':  '收益曲线图',
        'position': '持仓状态图',
        'signals':  '价格信号图',
        'summary':  '总览图    ',
    }
    for key, path in chart_paths.items():
        print(f"  {labels.get(key, key)}: {path}")
    print(f"  交易日志    : {result['log_path']}")
    print("=" * 60)

    return result, chart_paths


if __name__ == '__main__':
    main()
