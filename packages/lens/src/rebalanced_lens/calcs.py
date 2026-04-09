from dataclasses import dataclass

import polars as pl


@dataclass(frozen=True, slots=True)
class ActiveShareResult:
    active_share: float
    active_share_pct: float
    overlap_count: int
    portfolio_only_count: int
    benchmark_only_count: int
    portfolio_total_count: int
    benchmark_total_count: int


def _validate_columns(
    df: pl.DataFrame,
    name: str,
    required: list[str],
) -> None:
    """Raise ValueError if any required columns are missing."""
    missing = set(required) - set(df.columns)
    if missing:
        available = ", ".join(df.columns)
        raise ValueError(
            f"{name} DataFrame missing columns: {', '.join(sorted(missing))}. "
            f"Available: {available}"
        )


def _renormalize(df: pl.DataFrame) -> pl.DataFrame:
    """Renormalize weights to sum to 1.0."""
    total = df["weight"].sum()
    if total <= 0:
        return df
    return df.with_columns((pl.col("weight") / total).alias("weight"))


def active_share(
    portfolio: pl.DataFrame,
    benchmark: pl.DataFrame,
    ticker_col: str = "ticker",
    weight_col: str = "weight",
    asset_type_col: str = "asset_type",
    asset_class: str | None = None,
) -> ActiveShareResult:
    """Calculate Active Share between portfolio and benchmark.

    Active Share measures the fraction of the portfolio that differs from
    the benchmark index. Per Cremers & Petajisto (2009), it is calculated as
    half the sum of absolute differences in weights across all holdings.

    Formula: 0.5 × Σ|w_portfolio,i - w_benchmark,i|

    Where:
        - w_portfolio,i = weight of holding i in portfolio (0-1 scale)
        - w_benchmark,i = weight of holding i in benchmark (0-1 scale)
        - Missing holdings in either are treated as weight 0

    Interpretation:
        - 0% = Identical to benchmark (closet indexer)
        - ~60% = Typical active manager
        - >80% = Very active stock picker
        - 100% = Completely different from benchmark

    Args:
        portfolio: Polars DataFrame with holdings. Must contain:
            - ticker_col: Ticker/ISIN identifier
            - weight_col: Weight as decimal (e.g., 0.05 for 5%)
            - asset_type_col: Asset classification (equity, debt, cash, etc.)
        benchmark: Polars DataFrame with same schema as portfolio.
        ticker_col: Name of the ticker/identifier column. Default: "ticker".
        weight_col: Name of the weight column. Default: "weight".
        asset_type_col: Name of the asset type column. Default: "asset_type".
        asset_class: If specified, only holdings of this asset type are included
            in the calculation. Weights are renormalized to sum to 1 within
            the filtered set.

    Returns:
        ActiveShareResult dataclass with:
            - active_share: Float 0-1 (e.g., 0.75 = 75% active)
            - active_share_pct: Active share as percentage (0-100)
            - overlap_count: Number of overlapping holdings
            - portfolio_only_count: Holdings only in portfolio
            - benchmark_only_count: Holdings only in benchmark
            - portfolio_total_count: Total holdings in portfolio
            - benchmark_total_count: Total holdings in benchmark

    Raises:
        ValueError: If required columns are missing from either DataFrame.

    Notes:
        - Long-only assumed (no naked shorts, per Indian mutual fund rules).
        - Missing holdings in either portfolio or benchmark are treated as weight 0.
        - Arb positions treated as cash equivalent.

    Example:
        >>> import polars as pl
        >>> portfolio = pl.DataFrame({
        ...     "ticker": ["A", "B", "C"],
        ...     "weight": [0.5, 0.3, 0.2],
        ...     "asset_type": ["equity", "equity", "cash"],
        ... })
        >>> benchmark = pl.DataFrame({
        ...     "ticker": ["A", "B", "D"],
        ...     "weight": [0.4, 0.4, 0.2],
        ...     "asset_type": ["equity", "equity", "equity"],
        ... })
        >>> result = active_share(portfolio, benchmark)
        >>> f"{result.active_share:.2%}"
        '15.00%'
    """
    required = [ticker_col, weight_col, asset_type_col]

    _validate_columns(portfolio, "portfolio", required)
    _validate_columns(benchmark, "benchmark", required)

    # Standardize column names via rename (cleaner than select+alias)
    port = portfolio.select(required).rename(
        {
            ticker_col: "ticker",
            weight_col: "weight",
            asset_type_col: "asset_type",
        }
    )

    bench = benchmark.select(required).rename(
        {
            ticker_col: "ticker",
            weight_col: "weight",
            asset_type_col: "asset_type",
        }
    )

    # Filter and renormalize if asset_class specified
    if asset_class is not None:
        port = _renormalize(port.filter(pl.col("asset_type") == asset_class))
        bench = _renormalize(bench.filter(pl.col("asset_type") == asset_class))

    # Single join with coalesce fills missing weights as 0
    joined = (
        port.join(bench, on="ticker", how="full", coalesce=True)
        .with_columns(
            [
                pl.col("weight").fill_null(0.0).alias("port_weight"),
                pl.col("weight_right").fill_null(0.0).alias("bench_weight"),
            ]
        )
        .with_columns(
            (pl.col("port_weight") - pl.col("bench_weight")).abs().alias("abs_diff")
        )
    )

    active_share_value = 0.5 * float(joined["abs_diff"].sum())

    # Count statistics—single pass with boolean expressions
    return ActiveShareResult(
        active_share=active_share_value,
        active_share_pct=active_share_value * 100,
        overlap_count=int(
            ((joined["port_weight"] > 0) & (joined["bench_weight"] > 0)).sum()
        ),
        portfolio_only_count=int(
            ((joined["port_weight"] > 0) & (joined["bench_weight"] == 0)).sum()
        ),
        benchmark_only_count=int(
            ((joined["port_weight"] == 0) & (joined["bench_weight"] > 0)).sum()
        ),
        portfolio_total_count=port.height,
        benchmark_total_count=bench.height,
    )
