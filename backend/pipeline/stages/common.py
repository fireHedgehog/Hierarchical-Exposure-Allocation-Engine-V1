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
}

PRICE_SOFT_MAX_AGE_DAYS = 5
PRICE_HARD_MAX_AGE_DAYS = 10
# 10 years gives factor_engine's 1M/3M/6M momentum plenty of tail history and
# gives the per-symbol backtest a real multi-cycle window to trade, in one
# fetch per symbol (Yahoo returns the requested range in a single response,
# so this isn't N times slower than a 1-year fetch, just a bigger payload).
PRICE_FETCH_RANGE = "10y"


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
