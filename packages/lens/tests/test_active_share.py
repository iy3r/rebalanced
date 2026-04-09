import os

import polars as pl
import pytest
from rebalanced_lens.calcs import active_share

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def active_share_fund() -> pl.DataFrame:
    return pl.read_parquet(os.path.join(FIXTURES_DIR, "INF226401018.parquet"))


@pytest.fixture
def active_share_etf() -> pl.DataFrame:
    return pl.read_parquet(os.path.join(FIXTURES_DIR, "INF247L01BU1.parquet"))


def test_active_share_complete_holdings(
    active_share_fund: pl.DataFrame, active_share_etf: pl.DataFrame
) -> None:
    result = active_share(active_share_fund, active_share_etf)

    print(f"\nComplete holdings active share: {result.active_share_pct:.1f}%")

    # Fund has ~82% active share vs broad index (very active)
    assert result.active_share == pytest.approx(0.82, abs=0.01)


def test_active_share_equity_only(
    active_share_fund: pl.DataFrame, active_share_etf: pl.DataFrame
) -> None:
    result = active_share(active_share_fund, active_share_etf, asset_class="equity")

    print(f"\nEquity-only active share: {result.active_share_pct:.1f}%")

    # Equity-only active share is ~81% (similar, since cash/debt is small portion)
    assert result.active_share == pytest.approx(0.81, abs=0.01)
