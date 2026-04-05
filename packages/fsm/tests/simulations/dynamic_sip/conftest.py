from datetime import date
from pathlib import Path
from typing import NamedTuple

import polars as pl
import pytest

SIM_START = date(2006, 4, 1)
SIM_END = date(2026, 3, 31)
RSI_PERIOD = 14


class MarketDay(NamedTuple):
    day_idx: int
    date: pl.Date
    nav: float
    is_month_start: bool
    rsi: float | None


def _calculate_rsi(nav: pl.Series, period: int = RSI_PERIOD) -> pl.Series:
    deltas = nav.diff().to_list()
    gains = [max(d, 0) if d is not None else 0.0 for d in deltas]
    losses = [max(-d, 0) if d is not None else 0.0 for d in deltas]
    rsi_values: list[float | None] = [None] * len(nav)

    avg_gain = sum(gains[1 : period + 1]) / period
    avg_loss = sum(losses[1 : period + 1]) / period

    if avg_loss == 0:
        rsi_values[period] = 100.0
    else:
        rsi_values[period] = 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))

    for i in range(period + 1, len(nav)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        rsi_values[i] = (
            100.0 if avg_loss == 0 else 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))
        )

    return pl.Series(rsi_values)


def _load_nav_data() -> pl.DataFrame:
    conftest_path = Path(__file__).resolve()
    parquet_path = (
        conftest_path.parents[4] / "core" / "tests" / "fixtures" / "niftybees.parquet"
    )
    assert parquet_path.exists(), f"Parquet not found: {parquet_path}"
    df = pl.read_parquet(parquet_path)
    growth_factors = 1 + df["daily_ret"] / 100
    nav_series = (10.0 * growth_factors.cum_prod()).round(4)
    rsi_series = _calculate_rsi(nav_series)

    dates = df["date"]
    is_month_start = (
        (dates.dt.year() != dates.dt.year().shift(1))
        | (dates.dt.month() != dates.dt.month().shift(1))
    ).fill_null(True)

    df = df.with_columns(
        nav=nav_series,
        rsi=rsi_series,
        is_month_start=is_month_start,
    )

    return df.filter((pl.col("date") >= SIM_START) & (pl.col("date") <= SIM_END))


@pytest.fixture(scope="session")
def nav_history() -> pl.DataFrame:
    return _load_nav_data()


@pytest.fixture
def market_days(nav_history: pl.DataFrame) -> list[MarketDay]:
    return [
        MarketDay(
            day_idx=row["day_idx"],
            date=row["date"],
            nav=row["nav"],
            is_month_start=row["is_month_start"],
            rsi=row["rsi"],
        )
        for row in nav_history.with_row_index(name="day_idx").iter_rows(named=True)
    ]
