"""Compile a reviewed, disposable stage-2 universe from issuer sources.

The compiler deliberately distinguishes two questions:

* Did the issuer source disclose a full roster and did we account for every
  source row?
* Did every price-eligible source row map to a provider-compatible symbol?

Rejected mappings and deliberately excluded rows are retained in the output
metadata. A failed mapping can therefore never be mistaken for a complete
price universe merely because a scraper returned fewer rows.

Sources:
  - State Street official daily holdings XLSX: SPY, DIA, the eleven Select
    Sector SPDRs, and XBI.
  - Nasdaq official Nasdaq-100 list API: QQQ.
  - iShares official latest-holdings CSV: SOXX and IGV.
  - ARK official static holdings CSV: ARKX.
  - First Trust official server-rendered holdings page: CIBR.

Run from the repository root with a platform-appropriate Python executable:

    python -m backend.universe.compile_stage2_universe

The destination is resolved relative to this file and atomically replaced.
Staging is deliberately mutable; Git history is sufficient recovery.
"""
from __future__ import annotations

import csv
import io
import json
import posixpath
import re
import zipfile
from collections.abc import Mapping
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, BinaryIO
from xml.etree import ElementTree as ET

import httpx

XLSX_NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
OFFICE_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}

FROZEN_AT = "2026-08-29"
STAGE = "stage-2"
UNIVERSE_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_PATH = UNIVERSE_DIR / f"{STAGE}-{FROZEN_AT}.json"

# This is deliberately a US/Yahoo-compatible price-symbol pattern, not a
# claim about every identifier an international ETF issuer may disclose.
_PRICE_SYMBOL_PATTERN = re.compile(r"^[A-Z]{1,5}([.\-][A-Z])?$")

SSGA_INDEX_ANCHORS = {"SPY": "index", "DIA": "index"}
SSGA_SECTOR_ANCHORS = {
    "XLB": "thematic_etf",
    "XLC": "thematic_etf",
    "XLE": "thematic_etf",
    "XLF": "thematic_etf",
    "XLI": "thematic_etf",
    "XLK": "thematic_etf",
    "XLP": "thematic_etf",
    "XLRE": "thematic_etf",
    "XLU": "thematic_etf",
    "XLV": "thematic_etf",
    "XLY": "thematic_etf",
    "XBI": "thematic_etf",
}
ISHARES_ANCHORS = {
    "SOXX": "https://www.ishares.com/us/products/239705/ishares-semiconductor-etf/latest-holdings.csv",
    "IGV": "https://www.ishares.com/us/products/239771/ishares-expanded-tech-software-sector-etf/latest-holdings.csv",
}
ARK_ANCHORS = {
    "ARKX": (
        "https://assets.ark-funds.com/fund-documents/funds-etf-csv/"
        "ARK_SPACE_%26_DEFENSE_INNOVATION_ETF_ARKX_HOLDINGS.csv"
    ),
}
FIRST_TRUST_ANCHORS = {
    "CIBR": "https://www.ftportfolios.com/Retail/Etf/EtfHoldings.aspx?Ticker=CIBR",
}
OFFICIAL_ETF_ANCHORS = {
    **{ticker: "thematic_etf" for ticker in ISHARES_ANCHORS},
    **{ticker: "thematic_etf" for ticker in ARK_ANCHORS},
    **{ticker: "thematic_etf" for ticker in FIRST_TRUST_ANCHORS},
}
ANCHOR_KINDS = {
    **SSGA_INDEX_ANCHORS,
    **SSGA_SECTOR_ANCHORS,
    "QQQ": "index",
    **OFFICIAL_ETF_ANCHORS,
}

# Issuers commonly disclose Bloomberg/local-exchange identifiers. These are
# explicit, reviewed translations into the Yahoo symbols used by the staging
# price library. Unknown identifiers remain rejected; they are never guessed.
PRICE_SYMBOL_OVERRIDES = {
    "ARKX": {
        "RKLB UQ": "RKLB",
        "GRMN UN": "GRMN",
        "6301": "6301.T",
        "2618": "2618.HK",
        # ARK publishes Thales under its local mnemonic while First Trust
        # publishes the same issuer as Bloomberg HO.FP. Yahoo's Paris identity
        # is HO.PA; without this cross-source normalization the one company is
        # compiled twice and the bare HO identity has no price series.
        "HO": "HO.PA",
    },
    "CIBR": {
        "HO.FP": "HO.PA",
        "4704.JP": "4704.T",
        "OTEX.CN": "OTEX.TO",
        "ATO.FP": "ATO.PA",
    },
}


def _normalize_price_symbol(raw: str) -> str | None:
    symbol = raw.strip().upper()
    if not _PRICE_SYMBOL_PATTERN.fullmatch(symbol):
        return None
    # State Street/iShares use a dot for US class shares while Yahoo uses a
    # hyphen. Foreign suffixes never reach this fallback; they require an
    # explicit issuer-specific override above.
    return symbol.replace(".", "-")


def _map_price_symbol(anchor: str, raw: str) -> str | None:
    source_identifier = raw.strip().upper()
    override = PRICE_SYMBOL_OVERRIDES.get(anchor, {}).get(source_identifier)
    if override is not None:
        return override
    return _normalize_price_symbol(source_identifier)


def _parse_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text in {"-", "--", "N/A", "n/a"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    text = text.replace(",", "").replace("$", "").replace("%", "").strip()
    try:
        parsed = float(text)
    except ValueError:
        return None
    return -parsed if negative else parsed


def _normalize_as_of(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = re.sub(r"^As of\s+", "", str(raw).strip(), flags=re.IGNORECASE)
    value = value.strip('" ,')
    for date_format in (
        "%Y-%m-%d",
        "%d-%b-%Y",
        "%b %d, %Y",
        "%b %d, %Y %I:%M %p",
        "%m/%d/%Y",
    ):
        try:
            return datetime.strptime(value, date_format).date().isoformat()
        except ValueError:
            continue
    return None


def _response_text(response: httpx.Response) -> str:
    content = response.content
    if isinstance(content, bytes):
        return content.decode("utf-8-sig")
    return str(content)


def _clean_source_data(row: Mapping[Any, Any]) -> dict[str, Any]:
    return {
        str(key): value.strip() if isinstance(value, str) else value
        for key, value in row.items()
        if key is not None and value not in (None, "")
    }


def _audit_row(
    *,
    source_identifier: str | None,
    name: str | None,
    reason: str,
    source_data: Mapping[Any, Any],
    security_id: str | None = None,
) -> dict[str, Any]:
    audit = {
        "source_identifier": source_identifier or None,
        "name": name or None,
        "reason": reason,
        "source_data": _clean_source_data(source_data),
    }
    if security_id:
        audit["security_id"] = security_id
    return audit


def _add_member(
    *,
    members: dict[str, dict[str, Any]],
    rejected_rows: list[dict[str, Any]],
    price_symbol: str,
    source_identifier: str,
    name: str,
    weight_pct: float | None,
    source_data: Mapping[Any, Any],
    security_id: str | None = None,
) -> bool:
    if price_symbol in members:
        rejected_rows.append(
            _audit_row(
                source_identifier=source_identifier,
                name=name,
                reason=f"duplicate_price_symbol:{price_symbol}",
                source_data=source_data,
                security_id=security_id,
            )
        )
        return False
    detail: dict[str, Any] = {
        "name": name,
        "weight_pct": weight_pct,
        "source_identifier": source_identifier,
    }
    if security_id:
        detail["security_id"] = security_id
    members[price_symbol] = detail
    return True


def _anchor_result(
    *,
    source: str,
    source_kind: str,
    source_declared_full: bool,
    source_as_of_raw: str | None,
    source_row_count: int,
    members: dict[str, dict[str, Any]],
    excluded_rows: list[dict[str, Any]],
    rejected_rows: list[dict[str, Any]],
    source_reported_count: int | None = None,
) -> dict[str, Any]:
    mapped_count = len(members)
    rejected_count = len(rejected_rows)
    excluded_count = len(excluded_rows)
    eligible_count = mapped_count + rejected_count
    accounted_count = eligible_count + excluded_count
    reported_count_matches = (
        source_reported_count is None or eligible_count == source_reported_count
    )
    source_roster_complete = (
        source_declared_full
        and source_row_count > 0
        and accounted_count == source_row_count
        and reported_count_matches
    )
    price_symbol_mapping_complete = eligible_count > 0 and rejected_count == 0
    if source_roster_complete:
        coverage_status = "full"
    elif source_row_count > 0:
        coverage_status = "partial_or_parse_mismatch"
    else:
        coverage_status = "unknown"
    return {
        "as_of": _normalize_as_of(source_as_of_raw),
        "source_as_of_raw": source_as_of_raw,
        "source": source,
        "source_kind": source_kind,
        "coverage_status": coverage_status,
        "source_row_count": source_row_count,
        "source_reported_count": source_reported_count,
        "eligible_row_count": eligible_count,
        "mapped_member_count": mapped_count,
        "excluded_row_count": excluded_count,
        "rejected_row_count": rejected_count,
        "weight_value_count": sum(
            detail["weight_pct"] is not None for detail in members.values()
        ),
        "source_roster_complete": source_roster_complete,
        "price_symbol_mapping_complete": price_symbol_mapping_complete,
        "complete_for_price_universe": (
            source_roster_complete and price_symbol_mapping_complete
        ),
        "excluded_rows": excluded_rows,
        "rejected_rows": rejected_rows,
        "members": members,
    }


def _first_worksheet_path(workbook: zipfile.ZipFile) -> str:
    workbook_root = ET.fromstring(workbook.read("xl/workbook.xml"))
    sheet = workbook_root.find(".//a:sheets/a:sheet", XLSX_NS)
    if sheet is not None:
        relationship_id = sheet.get(f"{{{OFFICE_REL_NS}}}id")
        if relationship_id:
            relationships = ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
            for relationship in relationships.findall("r:Relationship", PACKAGE_REL_NS):
                if relationship.get("Id") != relationship_id:
                    continue
                target = relationship.get("Target")
                if target:
                    if target.startswith("/"):
                        return target.lstrip("/")
                    return posixpath.normpath(posixpath.join("xl", target))
    candidates = sorted(
        name
        for name in workbook.namelist()
        if name.startswith("xl/worksheets/") and name.endswith(".xml")
    )
    if not candidates:
        raise ValueError("XLSX contains no worksheet XML.")
    return candidates[0]


def _column_index(cell_reference: str | None, fallback: int) -> int:
    if not cell_reference:
        return fallback
    match = re.match(r"([A-Z]+)", cell_reference.upper())
    if match is None:
        return fallback
    index = 0
    for character in match.group(1):
        index = index * 26 + ord(character) - ord("A") + 1
    return index - 1


def read_xlsx_rows(source: bytes | BinaryIO) -> list[list[str | None]]:
    """Read the first workbook worksheet from bytes without filesystem I/O."""
    stream: bytes | BinaryIO = io.BytesIO(source) if isinstance(source, bytes) else source
    with zipfile.ZipFile(stream) as workbook:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in workbook.namelist():
            root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
            for item in root.findall("a:si", XLSX_NS):
                texts = item.findall(".//a:t", XLSX_NS)
                shared.append("".join(text.text or "" for text in texts))

        sheet = ET.fromstring(workbook.read(_first_worksheet_path(workbook)))
        rows: list[list[str | None]] = []
        for row in sheet.findall(".//a:row", XLSX_NS):
            cells: list[str | None] = []
            for cell in row.findall("a:c", XLSX_NS):
                column = _column_index(cell.get("r"), len(cells))
                while len(cells) <= column:
                    cells.append(None)
                cell_type = cell.get("t")
                if cell_type == "inlineStr":
                    texts = cell.findall(".//a:is//a:t", XLSX_NS)
                    value = "".join(text.text or "" for text in texts)
                else:
                    raw_value = cell.find("a:v", XLSX_NS)
                    value = raw_value.text if raw_value is not None else None
                    if cell_type == "s" and value is not None:
                        value = shared[int(value)]
                cells[column] = value
            rows.append(cells)
        return rows


def _find_as_of(rows: list[list[str | None]]) -> str | None:
    for row in rows:
        for index, raw_cell in enumerate(row):
            if raw_cell is None:
                continue
            cell = str(raw_cell).strip()
            if cell.lower() == "as of" and index + 1 < len(row) and row[index + 1]:
                return str(row[index + 1]).strip()
            match = re.search(r"\bAs of\s+(.+)$", cell, flags=re.IGNORECASE)
            if match:
                return match.group(1).strip()
    return None


def _ssga_exclusion_reason(name: str, source_identifier: str) -> str | None:
    upper_name = name.upper()
    if upper_name in {
        "US DOLLAR",
        "U.S. DOLLAR",
        "USD CASH",
        "POUND STERLING",
    }:
        return "cash_or_currency"
    if "MONEY MARKET" in upper_name:
        return "cash_or_cash_equivalent"
    if upper_name.startswith("CONTRA "):
        return "contingent_value_right"
    if "EARNOUT" in upper_name:
        return "earnout_right"
    if "FUTURE" in upper_name:
        return "derivative_future"
    if re.fullmatch(r"[A-Z]{2,6}[FGHJKMNQUVXZ]\d{1,2}", source_identifier.upper()):
        return "derivative_future"
    if source_identifier.startswith("$"):
        return "cash_or_currency"
    return None


def fetch_ssga(ticker: str) -> dict[str, Any]:
    url = (
        "https://www.ssga.com/us/en/individual/etfs/library-content/products/"
        f"fund-data/etfs/us/holdings-daily-us-en-{ticker.lower()}.xlsx"
    )
    response = httpx.get(
        url,
        timeout=20,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()
    rows = read_xlsx_rows(response.content)
    header_index = next(
        (
            index
            for index, row in enumerate(rows)
            if "Name" in row and "Ticker" in row
        ),
        None,
    )
    if header_index is None:
        raise ValueError(f"{ticker}: State Street workbook has no Name/Ticker header.")
    header = rows[header_index]
    name_column = header.index("Name")
    ticker_column = header.index("Ticker")
    weight_column = next(
        (
            index
            for index, value in enumerate(header)
            if value and "weight" in str(value).lower()
        ),
        None,
    )

    members: dict[str, dict[str, Any]] = {}
    excluded_rows: list[dict[str, Any]] = []
    rejected_rows: list[dict[str, Any]] = []
    source_rows: list[list[str | None]] = []
    for row in rows[header_index + 1 :]:
        name = str(row[name_column]).strip() if name_column < len(row) and row[name_column] else ""
        source_identifier = (
            str(row[ticker_column]).strip()
            if ticker_column < len(row) and row[ticker_column]
            else ""
        )
        if not name and not source_identifier:
            # State Street appends marketing/legal text after the first blank
            # row following the contiguous holdings table. Continuing would
            # count that prose as unmapped securities.
            if source_rows:
                break
            continue
        source_rows.append(row)
        source_data = {
            str(column_name): row[index]
            for index, column_name in enumerate(header)
            if column_name and index < len(row) and row[index] is not None
        }
        exclusion_reason = _ssga_exclusion_reason(name, source_identifier)
        if exclusion_reason:
            excluded_rows.append(
                _audit_row(
                    source_identifier=source_identifier,
                    name=name,
                    reason=exclusion_reason,
                    source_data=source_data,
                )
            )
            continue
        price_symbol = _map_price_symbol(ticker, source_identifier)
        if price_symbol is None:
            rejected_rows.append(
                _audit_row(
                    source_identifier=source_identifier,
                    name=name,
                    reason="unmapped_price_symbol",
                    source_data=source_data,
                )
            )
            continue
        weight = (
            _parse_number(row[weight_column])
            if weight_column is not None and weight_column < len(row)
            else None
        )
        _add_member(
            members=members,
            rejected_rows=rejected_rows,
            price_symbol=price_symbol,
            source_identifier=source_identifier,
            name=name,
            weight_pct=weight,
            source_data=source_data,
        )

    return _anchor_result(
        source=url,
        source_kind="issuer_full_holdings_xlsx",
        source_declared_full=True,
        source_as_of_raw=_find_as_of(rows[:header_index]),
        source_row_count=len(source_rows),
        members=members,
        excluded_rows=excluded_rows,
        rejected_rows=rejected_rows,
    )


def fetch_qqq() -> dict[str, Any]:
    url = "https://api.nasdaq.com/api/quote/list-type/nasdaq100"
    response = httpx.get(
        url,
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    nested_data = data.get("data") if isinstance(data, dict) else None
    rows = nested_data.get("rows") if isinstance(nested_data, dict) else None
    if not isinstance(rows, list):
        raise ValueError("QQQ: Nasdaq response has no list of constituent rows.")

    members: dict[str, dict[str, Any]] = {}
    excluded_rows: list[dict[str, Any]] = []
    rejected_rows: list[dict[str, Any]] = []
    market_caps: dict[str, float | None] = {}
    for row in rows:
        if not isinstance(row, dict):
            rejected_rows.append(
                _audit_row(
                    source_identifier=None,
                    name=None,
                    reason="malformed_source_row",
                    source_data={"value": repr(row)},
                )
            )
            continue
        source_identifier = str(row.get("symbol") or "").strip()
        name = str(row.get("companyName") or "").strip()
        price_symbol = _map_price_symbol("QQQ", source_identifier)
        if price_symbol is None:
            rejected_rows.append(
                _audit_row(
                    source_identifier=source_identifier,
                    name=name,
                    reason="unmapped_price_symbol",
                    source_data=row,
                )
            )
            continue
        added = _add_member(
            members=members,
            rejected_rows=rejected_rows,
            price_symbol=price_symbol,
            source_identifier=source_identifier,
            name=name,
            weight_pct=None,
            source_data=row,
        )
        if added:
            market_caps[price_symbol] = _parse_number(row.get("marketCap"))

    valid_market_caps = [value for value in market_caps.values() if value is not None]
    caps_complete = len(valid_market_caps) == len(members)
    total_market_cap = sum(valid_market_caps)
    if caps_complete and not rejected_rows and total_market_cap > 0:
        for symbol, market_cap in market_caps.items():
            assert market_cap is not None
            members[symbol]["weight_pct"] = round(market_cap / total_market_cap * 100, 4)

    as_of_raw = data.get("date") if isinstance(data, dict) else None
    result = _anchor_result(
        source=url,
        source_kind="official_index_list_api",
        source_declared_full=True,
        source_as_of_raw=str(as_of_raw) if as_of_raw else None,
        source_row_count=len(rows),
        members=members,
        excluded_rows=excluded_rows,
        rejected_rows=rejected_rows,
    )
    result["market_cap_value_count"] = len(valid_market_caps)
    result["market_cap_values_complete"] = caps_complete
    return result


def _csv_preamble_value(lines: list[str], key: str) -> str | None:
    for line in lines:
        parsed = next(csv.reader([line]), [])
        if parsed and parsed[0].strip() == key and len(parsed) > 1:
            return parsed[1].strip()
    return None


def fetch_ishares(ticker: str, url: str | None = None) -> dict[str, Any]:
    source_url = url or ISHARES_ANCHORS[ticker]
    response = httpx.get(
        source_url,
        timeout=20,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()
    text = _response_text(response)
    lines = text.splitlines()
    header_index = next(
        (
            index
            for index, line in enumerate(lines)
            if line.lstrip("\ufeff").startswith("Ticker,Name,Sector,Asset Class,")
        ),
        None,
    )
    if header_index is None:
        raise ValueError(f"{ticker}: iShares CSV has no holdings header.")
    source_as_of_raw = _csv_preamble_value(lines[:header_index], "Fund Holdings as of")
    reader = csv.DictReader(io.StringIO("\n".join(lines[header_index:])))
    source_rows = [
        row
        for row in reader
        if any(row.get(column) for column in ("Ticker", "Name", "Asset Class"))
    ]

    members: dict[str, dict[str, Any]] = {}
    excluded_rows: list[dict[str, Any]] = []
    rejected_rows: list[dict[str, Any]] = []
    for row in source_rows:
        source_identifier = str(row.get("Ticker") or "").strip()
        name = str(row.get("Name") or "").strip()
        asset_class = str(row.get("Asset Class") or "").strip()
        if asset_class.lower() != "equity":
            reason_class = re.sub(r"\s+", "_", asset_class.lower()) or "unknown"
            excluded_rows.append(
                _audit_row(
                    source_identifier=source_identifier,
                    name=name,
                    reason=f"non_equity_asset_class:{reason_class}",
                    source_data=row,
                )
            )
            continue
        price_symbol = _map_price_symbol(ticker, source_identifier)
        if price_symbol is None:
            rejected_rows.append(
                _audit_row(
                    source_identifier=source_identifier,
                    name=name,
                    reason="unmapped_price_symbol",
                    source_data=row,
                )
            )
            continue
        _add_member(
            members=members,
            rejected_rows=rejected_rows,
            price_symbol=price_symbol,
            source_identifier=source_identifier,
            name=name,
            weight_pct=_parse_number(row.get("Weight (%)")),
            source_data=row,
        )

    return _anchor_result(
        source=source_url,
        source_kind="issuer_full_holdings_csv",
        source_declared_full=True,
        source_as_of_raw=source_as_of_raw,
        source_row_count=len(source_rows),
        members=members,
        excluded_rows=excluded_rows,
        rejected_rows=rejected_rows,
    )


def _lowercase_csv_row(row: Mapping[Any, Any]) -> dict[str, Any]:
    return {
        str(key).strip().lower(): value.strip() if isinstance(value, str) else value
        for key, value in row.items()
        if key is not None
    }


def _ark_exclusion_reason(source_identifier: str, name: str, security_id: str) -> str | None:
    upper_name = name.upper()
    if not source_identifier and (
        "TRSY" in upper_name or "TREASURY" in upper_name or "CASH" in upper_name
    ):
        return "cash_or_cash_equivalent"
    if (
        source_identifier.upper() == "SPCX"
        and security_id == "84615Q103"
        and "SPACE EXPLORATION TECHN" in upper_name
    ):
        return "private_security"
    return None


def fetch_ark(ticker: str = "ARKX", url: str | None = None) -> dict[str, Any]:
    source_url = url or ARK_ANCHORS[ticker]
    response = httpx.get(
        source_url,
        timeout=20,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()
    rows = [
        _lowercase_csv_row(row)
        for row in csv.DictReader(io.StringIO(_response_text(response)))
    ]
    source_rows = [row for row in rows if row.get("fund") == ticker]
    if not source_rows:
        raise ValueError(f"{ticker}: ARK CSV contains no fund rows.")
    as_of_values = {str(row.get("date") or "").strip() for row in source_rows}
    as_of_values.discard("")
    source_as_of_raw = next(iter(as_of_values)) if len(as_of_values) == 1 else None

    members: dict[str, dict[str, Any]] = {}
    excluded_rows: list[dict[str, Any]] = []
    rejected_rows: list[dict[str, Any]] = []
    for row in source_rows:
        source_identifier = str(row.get("ticker") or "").strip()
        name = str(row.get("company") or "").strip()
        security_id = str(row.get("cusip") or "").strip()
        exclusion_reason = _ark_exclusion_reason(source_identifier, name, security_id)
        if exclusion_reason:
            excluded_rows.append(
                _audit_row(
                    source_identifier=source_identifier,
                    name=name,
                    reason=exclusion_reason,
                    source_data=row,
                    security_id=security_id,
                )
            )
            continue
        if not source_identifier:
            rejected_rows.append(
                _audit_row(
                    source_identifier=None,
                    name=name,
                    reason="missing_source_identifier",
                    source_data=row,
                    security_id=security_id,
                )
            )
            continue
        price_symbol = _map_price_symbol(ticker, source_identifier)
        if price_symbol is None:
            rejected_rows.append(
                _audit_row(
                    source_identifier=source_identifier,
                    name=name,
                    reason="unmapped_price_symbol",
                    source_data=row,
                    security_id=security_id,
                )
            )
            continue
        _add_member(
            members=members,
            rejected_rows=rejected_rows,
            price_symbol=price_symbol,
            source_identifier=source_identifier,
            name=name,
            weight_pct=_parse_number(row.get("weight (%)")),
            source_data=row,
            security_id=security_id,
        )

    return _anchor_result(
        source=source_url,
        source_kind="issuer_full_holdings_csv",
        source_declared_full=True,
        source_as_of_raw=source_as_of_raw,
        source_row_count=len(source_rows),
        members=members,
        excluded_rows=excluded_rows,
        rejected_rows=rejected_rows,
    )


class _FirstTrustHoldingsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.page_text_parts: list[str] = []
        self.tables: list[list[list[str]]] = []
        self._table_depth = 0
        self._current_table: list[list[str]] | None = None
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "table":
            if self._table_depth:
                self._table_depth += 1
            elif "fundSilverGrid" in (attributes.get("class") or "").split():
                self._table_depth = 1
                self._current_table = []
        if not self._table_depth:
            return
        if tag == "tr":
            self._current_row = []
        elif tag in {"td", "th"} and self._current_row is not None:
            self._current_cell = []

    def handle_endtag(self, tag: str) -> None:
        if not self._table_depth:
            return
        if tag in {"td", "th"} and self._current_cell is not None:
            assert self._current_row is not None
            self._current_row.append(" ".join("".join(self._current_cell).split()))
            self._current_cell = None
        elif tag == "tr" and self._current_row is not None:
            if any(self._current_row):
                assert self._current_table is not None
                self._current_table.append(self._current_row)
            self._current_row = None
        elif tag == "table":
            self._table_depth -= 1
            if self._table_depth == 0 and self._current_table is not None:
                self.tables.append(self._current_table)
                self._current_table = None

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.page_text_parts.append(data.strip())
        if self._current_cell is not None:
            self._current_cell.append(data)

    @property
    def page_text(self) -> str:
        return " ".join(self.page_text_parts)


def fetch_first_trust(ticker: str = "CIBR", url: str | None = None) -> dict[str, Any]:
    source_url = url or FIRST_TRUST_ANCHORS[ticker]
    response = httpx.get(
        source_url,
        timeout=20,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()
    parser = _FirstTrustHoldingsParser()
    parser.feed(_response_text(response))
    holdings_table: list[list[str]] | None = None
    header_index: int | None = None
    for table in parser.tables:
        candidate_header_index = next(
            (
                index
                for index, row in enumerate(table)
                if any("Security Name" in cell for cell in row)
                and any("Identifier" in cell for cell in row)
            ),
            None,
        )
        if candidate_header_index is not None:
            holdings_table = table
            header_index = candidate_header_index
            break
    if holdings_table is None or header_index is None:
        raise ValueError(f"{ticker}: First Trust page has no holdings table header.")
    header = holdings_table[header_index]
    source_rows = [row for row in holdings_table[header_index + 1 :] if any(row)]
    as_of_match = re.search(
        r"Holdings of the Fund as of\s+(\d{1,2}/\d{1,2}/\d{4})",
        parser.page_text,
        flags=re.IGNORECASE,
    )
    count_match = re.search(
        r"Total Number of Holdings\s*\(excluding cash\)\s*:\s*(\d+)",
        parser.page_text,
        flags=re.IGNORECASE,
    )
    source_as_of_raw = as_of_match.group(1) if as_of_match else None
    source_reported_count = int(count_match.group(1)) if count_match else None

    members: dict[str, dict[str, Any]] = {}
    excluded_rows: list[dict[str, Any]] = []
    rejected_rows: list[dict[str, Any]] = []
    for row in source_rows:
        source_data = {
            header[index] if index < len(header) else f"column_{index + 1}": value
            for index, value in enumerate(row)
        }
        if len(row) < 7:
            rejected_rows.append(
                _audit_row(
                    source_identifier=row[1] if len(row) > 1 else None,
                    name=row[0] if row else None,
                    reason="malformed_source_row",
                    source_data=source_data,
                )
            )
            continue
        name, source_identifier, security_id, classification = row[:4]
        if classification.lower() == "other" or source_identifier.startswith("$"):
            excluded_rows.append(
                _audit_row(
                    source_identifier=source_identifier,
                    name=name,
                    reason="cash_or_currency",
                    source_data=source_data,
                    security_id=security_id,
                )
            )
            continue
        price_symbol = _map_price_symbol(ticker, source_identifier)
        if price_symbol is None:
            rejected_rows.append(
                _audit_row(
                    source_identifier=source_identifier,
                    name=name,
                    reason="unmapped_price_symbol",
                    source_data=source_data,
                    security_id=security_id,
                )
            )
            continue
        _add_member(
            members=members,
            rejected_rows=rejected_rows,
            price_symbol=price_symbol,
            source_identifier=source_identifier,
            name=name,
            weight_pct=_parse_number(row[6]),
            source_data=source_data,
            security_id=security_id,
        )

    return _anchor_result(
        source=source_url,
        source_kind="issuer_server_rendered_full_holdings_html",
        source_declared_full=source_reported_count is not None,
        source_as_of_raw=source_as_of_raw,
        source_row_count=len(source_rows),
        source_reported_count=source_reported_count,
        members=members,
        excluded_rows=excluded_rows,
        rejected_rows=rejected_rows,
    )


def build_draft(
    anchors: Mapping[str, dict[str, Any]],
    *,
    compiled_at: str | None = None,
) -> dict[str, Any]:
    all_symbols: dict[str, dict[str, Any]] = {}
    for anchor, info in anchors.items():
        for symbol, detail in info["members"].items():
            entry = all_symbols.setdefault(
                symbol,
                {"name": detail["name"], "memberships": []},
            )
            membership: dict[str, Any] = {
                "anchor": anchor,
                "anchor_kind": ANCHOR_KINDS[anchor],
                "weight_pct": detail["weight_pct"],
                "source_identifier": detail["source_identifier"],
            }
            if detail.get("security_id"):
                membership["security_id"] = detail["security_id"]
            entry["memberships"].append(membership)

    anchor_sources: dict[str, dict[str, Any]] = {}
    for anchor, info in anchors.items():
        metadata = {key: value for key, value in info.items() if key != "members"}
        metadata["anchor_kind"] = ANCHOR_KINDS[anchor]
        metadata["count"] = len(info["members"])
        anchor_sources[anchor] = metadata

    return {
        "stage": STAGE,
        "frozen_at": FROZEN_AT,
        "compiled_at": compiled_at or datetime.now(timezone.utc).isoformat(),
        "method": (
            "State Street official daily holdings XLSX; Nasdaq official Nasdaq-100 list API; "
            "iShares official latest-holdings CSV; ARK official static holdings CSV; First "
            "Trust official server-rendered holdings HTML. Source-roster completeness and "
            "price-symbol mapping completeness are audited separately; every rejected or "
            "deliberately excluded source row is retained in anchor_sources."
        ),
        "mutability": (
            "Disposable staging snapshot; it may be regenerated or replaced after review. "
            "Git history is sufficient recovery."
        ),
        "anchor_sources": anchor_sources,
        "total_unique_symbols": len(all_symbols),
        "symbols": [
            {
                "symbol": symbol,
                "name": entry["name"],
                "memberships": sorted(
                    entry["memberships"], key=lambda membership: membership["anchor"]
                ),
            }
            for symbol, entry in sorted(all_symbols.items())
        ],
    }


def compile_universe() -> dict[str, Any]:
    anchors: dict[str, dict[str, Any]] = {}
    for ticker in [*SSGA_INDEX_ANCHORS, *SSGA_SECTOR_ANCHORS]:
        anchors[ticker] = fetch_ssga(ticker)
        print(
            f"{ticker}: {len(anchors[ticker]['members'])} mapped members "
            f"from {anchors[ticker]['source_row_count']} source rows, "
            f"as of {anchors[ticker]['as_of']}"
        )
    anchors["QQQ"] = fetch_qqq()
    print(
        f"QQQ: {len(anchors['QQQ']['members'])} mapped members "
        f"from {anchors['QQQ']['source_row_count']} source rows, "
        f"as of {anchors['QQQ']['as_of']}"
    )
    for ticker, url in ISHARES_ANCHORS.items():
        anchors[ticker] = fetch_ishares(ticker, url)
    for ticker, url in ARK_ANCHORS.items():
        anchors[ticker] = fetch_ark(ticker, url)
    for ticker, url in FIRST_TRUST_ANCHORS.items():
        anchors[ticker] = fetch_first_trust(ticker, url)
    for ticker in [*ISHARES_ANCHORS, *ARK_ANCHORS, *FIRST_TRUST_ANCHORS]:
        print(
            f"{ticker}: {len(anchors[ticker]['members'])} mapped members "
            f"from {anchors[ticker]['source_row_count']} source rows, "
            f"as of {anchors[ticker]['as_of']}"
        )
    return build_draft(anchors)


def write_staging_universe(
    draft: Mapping[str, Any], output_path: Path | str = DEFAULT_OUTPUT_PATH
) -> Path:
    path = Path(output_path)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(draft, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    temporary.replace(path)
    return path


def main() -> None:
    draft = compile_universe()
    output_path = write_staging_universe(draft)
    print(f"\nStaging file written to {output_path}")


if __name__ == "__main__":
    main()
