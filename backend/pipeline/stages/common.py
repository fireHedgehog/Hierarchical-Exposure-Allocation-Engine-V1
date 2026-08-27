from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from backend.providers.fred import FredObservation
from backend.providers.yahoo import PriceBar

# Shared constants, small helpers, and the StageOutcome contract every real
# pipeline stage in this package returns. Kept separate from the stage
# modules themselves so each stage file stays focused on its one job.

FredFetcher = Callable[..., list[FredObservation]]
PriceFetcher = Callable[..., list[PriceBar]]

CLOCK_SKEW_TOLERANCE_SECONDS = 300

# Coefficients (which series, how stale is too stale) are a naive first pass,
# same spirit as engine/regime/ — real series, real thresholds, open to
# revision once Milestone 4 (docs/engine-milestones.md) starts.
SERIES_METADATA: dict[str, dict[str, Any]] = {
    "INDPRO": {"frequency": "monthly", "max_age_days": 60, "label": "Industrial production index"},
    "CPIAUCSL": {"frequency": "monthly", "max_age_days": 60, "label": "Headline CPI (all urban consumers)"},
    "PPIACO": {"frequency": "monthly", "max_age_days": 60, "label": "Producer price index (all commodities)"},
    # BEA's PCE release trails CPI within each month and, unlike INDPRO/CPI/PPI,
    # can leave the freshest observation ~80-90 days old right before the next
    # print — observed for real on 2026-08-24 (84 days), not a bug.
    "PCEPILFE": {"frequency": "monthly", "max_age_days": 95, "label": "Core PCE price index"},
    "PAYEMS": {"frequency": "monthly", "max_age_days": 60, "label": "Total nonfarm payrolls"},
    "NFCI": {"frequency": "weekly", "max_age_days": 21, "label": "Chicago Fed national financial conditions index"},
    "VIXCLS": {"frequency": "daily", "max_age_days": 10, "label": "CBOE volatility index"},
    "DGS10": {"frequency": "daily", "max_age_days": 10, "label": "10-year Treasury constant maturity rate"},
    # docs/hypotheses/macro-research/ layer-1 input signals, added 2026-08-27.
    # All 14 verified live against the real FRED API before being wired in
    # here (a wrong series_id returns zero observations, which hard-fails
    # this stage's entire fetch, not just this one series). Real start dates
    # vary by series (SOFR: 2018, IORB: 2021 under this name, others reach
    # back decades) -- naming here does not claim a common history length,
    # only that real data exists somewhere in the fetch window.
    "WALCL": {"frequency": "weekly", "max_age_days": 21, "label": "Fed total assets (H.4.1)"},
    "WTREGEN": {"frequency": "weekly", "max_age_days": 21, "label": "Treasury General Account balance"},
    "DGS30": {"frequency": "daily", "max_age_days": 10, "label": "30-year Treasury constant maturity rate"},
    # BEA's GDP release is quarterly; a real live fetch on 2026-08-27 found
    # the freshest print (Q1 2026, period-dated 2026-04-01) already 147 days
    # old with no newer quarter available yet -- empirically corrected from
    # an initial 120-day guess, same pattern as PCEPILFE's own correction.
    "GDPC1": {"frequency": "quarterly", "max_age_days": 160, "label": "Real GDP"},
    "MTSDS133FMS": {"frequency": "monthly", "max_age_days": 60, "label": "Federal surplus or deficit (Monthly Treasury Statement)"},
    "ICSA": {"frequency": "weekly", "max_age_days": 21, "label": "Initial unemployment claims"},
    "T10YIE": {"frequency": "daily", "max_age_days": 10, "label": "10-year breakeven inflation rate"},
    "T5YIE": {"frequency": "daily", "max_age_days": 10, "label": "5-year breakeven inflation rate"},
    "DFII10": {"frequency": "daily", "max_age_days": 10, "label": "10-year TIPS real yield"},
    "DFII30": {"frequency": "daily", "max_age_days": 10, "label": "30-year TIPS real yield"},
    "BAMLH0A0HYM2": {"frequency": "daily", "max_age_days": 10, "label": "ICE BofA US high-yield OAS spread"},
    "BAMLC0A0CM": {"frequency": "daily", "max_age_days": 10, "label": "ICE BofA US corporate (IG) OAS spread"},
    "SOFR": {"frequency": "daily", "max_age_days": 10, "label": "Secured Overnight Financing Rate"},
    "IORB": {"frequency": "daily", "max_age_days": 10, "label": "Interest rate on reserve balances"},
    "DTWEXBGS": {"frequency": "daily", "max_age_days": 10, "label": "Trade-weighted broad U.S. dollar index"},
    # Real, objective Fed rate-decision ground truth -- lets macro-research
    # derive every real hike/cut directly from data (level changes on the
    # effective date), with no hand-curated meeting calendar needed. DFEDTAR
    # (single target, pre-2008-12-16) and DFEDTARU/DFEDTARL (target range,
    # after the Fed switched regimes) together cover 2004-2026 continuously.
    # max_age_days=None: this series was permanently discontinued 2008-12-15
    # (replaced by DFEDTARU/DFEDTARL) -- staleness has no real meaning here.
    "DFEDTAR": {"frequency": "daily", "max_age_days": None, "label": "Fed funds target rate (pre-2008 single value)"},
    "DFEDTARU": {"frequency": "daily", "max_age_days": 10, "label": "Fed funds target range, upper bound"},
    "DFEDTARL": {"frequency": "daily", "max_age_days": 10, "label": "Fed funds target range, lower bound"},
}

PRICE_SOFT_MAX_AGE_DAYS = 5
PRICE_HARD_MAX_AGE_DAYS = 10
# 10 years gives factor_engine's 1M/3M/6M momentum plenty of tail history and
# gives the per-symbol backtest a real multi-cycle window to trade, in one
# fetch per symbol (Yahoo returns the requested range in a single response,
# so this isn't N times slower than a 1-year fetch, just a bigger payload).
# Superseded for fetch_data's actual price fetch by STAGING_UNIVERSE_START_DATE
# below (2026-08-26) -- kept as the range_ fallback fetch_daily_bars still
# supports for any caller that wants a relative window instead of a fixed one.
PRICE_FETCH_RANGE = "10y"
# GLD's real, empirically-verified first trading day (fetched directly,
# 2026-08-26: earliest real bar from a full-history pull) -- the fixed
# common start date every staging symbol is fetched from, deliberately
# *not* each symbol's own longest available history. A controlled
# cross-asset comparison (e.g. gold's regime behavior vs. an equity index's,
# across 2008) needs every symbol aligned to the same real calendar window;
# letting older symbols (SPY, QQQ) reach further back than GLD can would
# produce an unaligned panel. This trades away real dot-com-era coverage
# (GLD didn't exist yet) for a clean, aligned comparison group from 2008
# onward -- an accepted, deliberate choice, not an oversight.
#
# fetch_daily_bars must be called with start_date=, not range_="max", to get
# genuine daily bars over this span: verified directly (2026-08-26) that
# Yahoo's range=max silently degrades interval=1d to a coarser real
# resolution once the span is many years (GLD's real full history via
# range=max returned only 262 bars; the identical span via explicit
# period1/period2 returned the real 5,467 true daily bars).
STAGING_UNIVERSE_START_DATE = "2004-12-01"
# Was 400 days (enough for regime_filter's trailing-12-month YoY calc, no
# more), then 10 years (too short for engine/research/'s significance
# testing at first: a monthly series like CPIAUCSL only yields ~11
# observations in 400 days, well below MIN_SAMPLES). Now matches
# STAGING_UNIVERSE_START_DATE (2026-08-26) so FRED macro observations and
# Yahoo symbol bars cover the same real window for genuine cross-regime
# (dot-com-excluded, 2008-included) comparison work.
FRED_OBSERVATION_WINDOW_DAYS = 7950


def _json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _security_id_for(symbol: str, category: str) -> str:
    slug = symbol.lower().replace("-", "")
    if category == "crypto_reference":
        return f"ref-{slug}"
    if category == "mega_cap_equity":
        return f"us-equity-{slug}"
    return f"us-etf-{symbol.lower()}"


def _asset_type_for(category: str) -> str:
    if category == "crypto_reference":
        return "Digital Asset Reference"
    if category == "mega_cap_equity":
        return "Equity"
    return "ETF"


@dataclass(frozen=True)
class StageOutcome:
    status: str
    message: str
    error_code: str | None = None
    records_read: int = 0
    records_written: int = 0
    dataset_snapshot_id: str | None = None
    desk_snapshot_id: str | None = None
