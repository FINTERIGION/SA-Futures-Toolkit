# SA Futures Toolkit

A Python-based backtesting framework for Soda Ash (SA) Futures traded on the China Zhengzhou Commodity Exchange (CZCE). Provides a complete pipeline for strategy development, simulation, performance analysis, and visualization.

## Features

- **Strategy Development** — Base class with clean API for implementing long/short futures strategies
- **Backtesting Engine** — Realistic simulation with futures-specific commissions, margin requirements, and contract multipliers
- **Performance Metrics** — Sharpe ratio, max drawdown, win rate, profit/loss ratio, and more
- **Visualization** — 5 types of charts (equity curve, returns, positions, signals, summary)
- **Data Management** — Automated data download and weighted price calculation from CZCE

## Project Structure

```
SA-Futures-Toolkit/
├── backtest/
│   ├── main.py               # Entry point — configure and run backtests here
│   ├── strategy.py           # Strategy implementations (edit to add your own)
│   ├── backtest_engine.py    # Core engine, analyzers, and metrics
│   ├── data_manager.py       # Data loading and backtrader feed
│   ├── plotting.py           # Chart generation
│   └── results/              # Auto-generated output (charts + trade logs)
├── data/                     # Auto-downloaded data (all contracts + weighted)
├── update.py                 # Download/refresh data from CZCE
└── requirements.txt
```

## Quick Start

### 1. Install dependencies

TA-Lib requires the C library to be installed separately before the Python package:

```bash
# Ubuntu/Debian
sudo apt-get install libta-lib-dev

# macOS
brew install ta-lib
```

Then install Python packages:

```bash
pip install -r requirements.txt
```

### 2. Run a backtest

```bash
python backtest/main.py
```

This runs the default `DoubleMaStrategy` over 2020–2024 and outputs:
- Performance metrics printed to the console
- 5 PNG charts saved to `backtest/results/`
- A CSV trade log saved to `backtest/results/`

## Configuration

All backtest parameters are set at the top of [backtest/main.py](backtest/main.py):

```python
# Strategy
STRATEGY = DoubleMaStrategy
STRATEGY_PARAMS = {
    'fast_period': 5,
    'slow_period': 20,
}

# Backtest period
START_DATE = '2020-01-01'
END_DATE   = '2024-12-31'

# Capital & trading
INITIAL_CASH        = 100_000.0
COMMISSION_RATE     = 0.0002   # 0.02%
MARGIN_RATE         = 0.15     # 15%
CONTRACT_MULTIPLIER = 20       # 20 tons/lot
TRADE_SIZE          = 1        # lots per trade

# Set to True to download/update data before running
UPDATE_DATA = True
```

## Writing a Custom Strategy

1. Open [backtest/strategy.py](backtest/strategy.py) and implement `MyStrategy`:

```python
class MyStrategy(FuturesStrategyBase):
    params = (
        ('my_param', 14),
    )

    def __init__(self):
        super().__init__()
        self.rsi = bt.indicators.RSI(period=self.p.my_param)

    def next(self):
        if self.rsi < 30:
            self.buy_signal()
        elif self.rsi > 70:
            self.sell_signal()
        elif abs(self.get_position_size()) > 0:
            self.close_signal()
```

2. Update `main.py` to use your strategy:

```python
STRATEGY = MyStrategy
STRATEGY_PARAMS = {'my_param': 14}
```

3. Run the backtest:

```bash
python backtest/main.py
```

### FuturesStrategyBase API

| Method | Description |
|--------|-------------|
| `buy_signal()` | Open a long position |
| `sell_signal()` | Open a short position |
| `close_signal()` | Close the current position |
| `get_position_size()` | Returns current net position (positive = long, negative = short) |

All signals are automatically recorded in `self.signal_log`.

## Included Strategies

| Strategy | Logic |
|----------|-------|
| `DoubleMaStrategy` | Fast MA / Slow MA crossover (trend-following) |
| `RsiMeanReversionStrategy` | RSI < 30 → buy, RSI > 70 → sell, close at RSI = 50 |
| `MyStrategy` | Empty template for custom strategies |

## Output

After each backtest run, the following files are saved to `backtest/results/`:

| File | Description |
|------|-------------|
| `equity_<timestamp>.png` | Account equity and drawdown over time |
| `return_<timestamp>.png` | Cumulative return and daily return bars |
| `position_<timestamp>.png` | Long/short position over time |
| `signals_<timestamp>.png` | Price chart with buy/sell markers |
| `summary_<timestamp>.png` | Combined 2×3 overview chart |
| `trades_<timestamp>.csv` | Full trade log with entry/exit details |

## License

MIT License
