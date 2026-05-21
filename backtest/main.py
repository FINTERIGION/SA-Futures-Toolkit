"""
Backtest Main Module
====================
Usage:
  1. Modify the parameters in the "Backtest Configuration" section below
  2. Change STRATEGY to the strategy class you want to run
  3. Run: python backtest/main.py

Directory structure:
  backtest/
    main.py            <- This file (backtest entry point; edit parameters here)
    strategy.py        <- Strategy module (write trading logic here)
    data_manager.py    <- Data management module
    backtest_engine.py <- Backtest engine and metrics calculation
    plotting.py        <- Chart plotting module
    results/           <- Backtest output directory (auto-created)
"""

import os
import sys

# Ensure the project root is on sys.path (so update.py and similar imports resolve)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_manager   import DataManager
from backtest_engine import BacktestEngine
from plotting       import BacktestPlotter

# Import strategies (change here to pick a different strategy)
from strategy import (
    DoubleMaStrategy,
    RsiMeanReversionStrategy,
    MyStrategy,
)


# ==============================================================================
# * Backtest Configuration (edit values here)
# ==============================================================================

# --- Strategy selection ---
STRATEGY = DoubleMaStrategy          # Replace with your strategy class, e.g. MyStrategy

# --- Strategy-specific parameters (match the strategy's `params`; leave empty to use defaults) ---
STRATEGY_PARAMS = {
    'fast_period': 5,
    'slow_period': 20,
    # 'rsi_period': 14,              # Example parameter for RsiMeanReversionStrategy
}

# --- Backtest range ---
START_DATE = '2020-01-01'            # Start date 'YYYY-MM-DD'
END_DATE   = '2024-12-31'            # End date   'YYYY-MM-DD'

# --- Capital and trading parameters ---
INITIAL_CASH         = 100_000.0     # Initial cash (CNY)
COMMISSION_RATE      = 0.0002        # Commission rate (0.02%)
MARGIN_RATE          = 0.15          # Margin ratio (15%)
CONTRACT_MULTIPLIER  = 20            # Contract multiplier (tons per lot)
TRADE_SIZE           = 1             # Lots per trade

# --- Data update ---
UPDATE_DATA = True                   # True = re-download data from the exchange

# --- Strategy name (used in file naming; use a distinct name per strategy) ---
STRATEGY_NAME = 'DoubleMA'

# --- Output directory ---
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')

# ==============================================================================
# Main program (usually no need to modify below)
# ==============================================================================

def main():
    print("=" * 60)
    print(f"  SA Futures Backtest Framework")
    print(f"  Strategy: {STRATEGY.__name__}  [{START_DATE} -> {END_DATE}]")
    print("=" * 60)

    # 1. Load data
    print("\n[1/4] Loading data ...")
    dm = DataManager(symbol='SA', update=UPDATE_DATA)
    data_feed = dm.get_bt_feed(start_date=START_DATE, end_date=END_DATE)
    price_df  = dm.load_dataframe(start_date=START_DATE, end_date=END_DATE)

    # 2. Configure backtest engine
    print("[2/4] Configuring backtest engine ...")
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

    # 3. Run backtest
    print("[3/4] Running backtest ...\n")
    result = engine.run()

    # 4. Plot charts
    print("\n[4/4] Plotting charts ...")
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

    # 5. Final summary
    print("\n" + "=" * 60)
    print("  Chart file paths")
    print("=" * 60)
    labels = {
        'equity':   'Equity Curve   ',
        'returns':  'Return Curve   ',
        'position': 'Position Chart ',
        'signals':  'Price & Signals',
        'summary':  'Summary Chart  ',
    }
    for key, path in chart_paths.items():
        print(f"  {labels.get(key, key)}: {path}")
    print(f"  Trade Log       : {result['log_path']}")
    print("=" * 60)

    return result, chart_paths


if __name__ == '__main__':
    main()
