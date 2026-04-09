"""rebalanced-lens: A financial calculations library for portfolio analysis.

This library provides metrics for portfolio analysis, organized by input data type:

- calcs: Core portfolio calculations (Active Share)

Example:
    >>> import polars as pl
    >>> from rebalanced_lens import active_share
    >>>
    >>> # Active Share calculation
    >>> portfolio = pl.DataFrame({
    ...     "ticker": ["A", "B"],
    ...     "weight": [0.6, 0.4],
    ...     "asset_type": ["equity", "equity"],
    ... })
    >>> benchmark = pl.DataFrame({
    ...     "ticker": ["A", "B"],
    ...     "weight": [0.5, 0.5],
    ...     "asset_type": ["equity", "equity"],
    ... })
    >>> result = active_share(portfolio, benchmark)
    >>> print(f"Active Share: {result['active_share_pct']:.1f}%")
    Active Share: 10.0%
"""

from rebalanced_lens.calcs import active_share

__all__ = [
    "active_share",
]

__version__ = "0.1.0"
