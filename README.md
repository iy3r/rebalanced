# rebalanced

**WIP**: A Python framework for market simulation and investment strategy modeling, built from composable primitives.

## Overview

`rebalanced` is a financial simulation framework built from **composable primitives** — reusable building blocks for modeling markets, portfolios, and trading strategies.

### Planned Primitives

- **Finite State Machines (FSM)**: Event-driven state transitions ✓ (implemented)
- **Event Streams**: Time-series data processing
- **Portfolio Models**: Pluggable representations of holdings
- **Simulation Engine**: Orchestration and lifecycle management
- **Analytics**: Reporting and visualization

### Use Cases

- **Strategy Backtesting**: Simulate trading strategies against historical data
- **Portfolio Rebalancing**: Model rebalancing rules as composable state machines
- **Market Simulation**: Build agent-based models of market behavior
- **Risk Analysis**: Stress-test strategies across scenarios

## Installation

```bash
pip install rebalanced
```

## Packages

This is a monorepo with the following packages:

| Package | Description |
|---------|-------------|
| `rebalanced` | Core namespace package |
| `rebalanced-core` | **TBD**: Simulation orchestration engine (planned) |
| `rebalanced-fsm` | Finite state machine primitives - event-driven state transitions |
| `rebalanced-cli` | **TBD**: Command-line interface for the simulation engine (planned) |
| `rebalanced-lens` | **TBD**: Analytics and reporting (planned) |

## Development

This project uses [uv](https://docs.astral.sh/uv/) for dependency management:

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Run linters
uv run ruff check .
```

## Status

🚧 This project is in early development. APIs are subject to change.

## License

Apache 2.0 License - see [LICENSE](LICENSE) for details.
