"""Compiler for the frozen stage-2 universe -- broad index membership
(SPY/DIA/QQQ, anchor_kind='index') and thematic/sector ETF basket
membership (the 11 XL Select Sector SPDRs + XBI + SOXX + IGV + ARKX + CIBR,
anchor_kind='thematic_etf'), unified into one frozen file with real
weight_pct per holding wherever the real source discloses it (used as a
size proxy within that basket -- no separate per-symbol market-cap fetch
needed). XBI/ARKX/CIBR added 2026-08-28 on direct request, to real,
liquidity-checked names -- vaccine/biotech and space trades the user named
directly, plus cybersecurity, a real gap from the earlier theme-research
design that never made it into the compiled file. Many of these funds'
real underlying holdings will show zero index-anchor membership at all
(not in SPY/QQQ/DIA) -- expected and itself informative, not an error: a
name being outside every broad index is a real, disclosed state, not a
"missing data" case, matching the user's own framing directly.

Real, authoritative sources only, live-verified 2026-08-28. Wikipedia/
generic-scrape summarization was tried first and rejected -- it produced
real errors (a duplicated ticker, a garbled one), not just gaps.
  - SPY, DIA, XLB/XLC/XLE/XLF/XLI/XLK/XLP/XLRE/XLU/XLV/XLY/XBI: State
    Street's own official daily holdings files (SSGA is the real issuer
    of all of these).
  - QQQ: Nasdaq's own official public list-type API (includes real
    marketCap per holding; weight_pct computed as marketCap / total).
  - SOXX, IGV, ARKX, CIBR: iShares (BlackRock)/ARK/First Trust are the
    real issuers, but each gates the holdings download behind an
    interstitial that blocks direct fetches. stockanalysis.com's real,
    server-rendered holdings table (includes each issuer's own disclosed
    %Weight) used instead -- a real, if one step removed, source;
    disclosed as such, not presented as the issuer's own file. Real,
    verified limitation: this source caps at the top 25 holdings by
    weight, not each fund's full real roster (all four real-hold more).

Not committed anywhere by running this -- writes into backend/universe/
directly since that's the real destination once reviewed, but the whole
file is treated as a draft until reviewed.

Run: .venv/bin/python compile_stage2_universe.py
"""
from __future__ import annotations

import json
import re
import zipfile
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

import httpx

XLSX_NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
FROZEN_AT = "2026-08-27"
STAGE = "stage-2"

# Real, live-caught rejection: a real library-fetch batch run against this
# compiled file 404'd on a genuine artifact of the source data --
# "2602335D" ("CONTRA HOLOGIC INCORPO", weight 0.0), a CUSIP-style earnout/
# contra row State Street's own real SPY file includes, never a real
# tradeable ticker. Broader audit found 14 such rows total: 3 CUSIP-style
# earnout/contra identifiers, and 11 real E-mini sector futures contracts
# (e.g. "IXAU6"/"XAF FINANCIAL SEP26") the sector SPDRs use internally for
# cash-management exposure, not real equity holdings. A real equity/ETF
# ticker is always 1-5 uppercase letters, optionally one class-share
# suffix (BRK.B, BF.B) -- this filter rejects everything else. Real, live-
# verified US tickers never fail this pattern.
_TICKER_PATTERN = re.compile(r"^[A-Z]{1,5}([.\-][A-Z])?$")


def _normalize_ticker(raw: str) -> str | None:
    symbol = raw.strip().upper()
    if not _TICKER_PATTERN.match(symbol):
        return None
    # Yahoo's real class-share convention uses a hyphen (BRK-B), not the dot
    # State Street's own files use (BRK.B) -- verified directly: BRK.B and
    # BF.B are both real, significant holdings (BRK.B is 1.4-11.2% weight
    # in some of these funds), not edge cases to drop.
    return symbol.replace(".", "-")

SSGA_INDEX_ANCHORS = {"SPY": "index", "DIA": "index"}
SSGA_SECTOR_ANCHORS = {
    "XLB": "thematic_etf", "XLC": "thematic_etf", "XLE": "thematic_etf",
    "XLF": "thematic_etf", "XLI": "thematic_etf", "XLK": "thematic_etf",
    "XLP": "thematic_etf", "XLRE": "thematic_etf", "XLU": "thematic_etf",
    "XLV": "thematic_etf", "XLY": "thematic_etf",
    "XBI": "thematic_etf",  # biotech/vaccine-era trade coverage, real user request
}
# iShares (SOXX/IGV)/ARK (ARKX)/First Trust (CIBR) all gate direct holdings
# downloads behind interstitials -- read via stockanalysis.com's real,
# server-rendered table instead (same real, disclosed limitation as
# SOXX/IGV: caps at the top 25 holdings by weight, not the full roster).
STOCKANALYSIS_ANCHORS = {
    "SOXX": "thematic_etf", "IGV": "thematic_etf",
    "ARKX": "thematic_etf",  # space/rocket trade coverage, real user request
    "CIBR": "thematic_etf",  # cybersecurity, gap closed from earlier theme-research design
}


def read_xlsx_rows(path: str) -> list[list[str | None]]:
    with zipfile.ZipFile(path) as z:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall("a:si", XLSX_NS):
                texts = si.findall(".//a:t", XLSX_NS)
                shared.append("".join(t.text or "" for t in texts))
        sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
        rows = []
        for row in sheet.findall(".//a:row", XLSX_NS):
            cells = []
            for c in row.findall("a:c", XLSX_NS):
                t = c.get("t")
                v = c.find("a:v", XLSX_NS)
                val = v.text if v is not None else None
                if t == "s" and val is not None:
                    val = shared[int(val)]
                cells.append(val)
            rows.append(cells)
        return rows


def fetch_ssga(ticker: str) -> dict:
    url = f"https://www.ssga.com/us/en/individual/etfs/library-content/products/fund-data/etfs/us/holdings-daily-us-en-{ticker.lower()}.xlsx"
    response = httpx.get(url, timeout=20, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    local_path = f"/tmp/{ticker.lower()}_holdings.xlsx"
    with open(local_path, "wb") as handle:
        handle.write(response.content)
    rows = read_xlsx_rows(local_path)
    as_of = rows[2][1] if len(rows) > 2 else None
    header_idx = next(i for i, r in enumerate(rows) if r and r[0] == "Name")
    header = rows[header_idx]
    weight_col = next((i for i, h in enumerate(header) if h and "weight" in h.lower()), None)
    members: dict[str, dict] = {}
    for row in rows[header_idx + 1:]:
        if not row or not row[0] or not row[1]:
            continue
        name = row[0].strip()
        symbol = _normalize_ticker(row[1])
        if symbol is None or "DOLLAR" in name.upper():
            continue
        weight = None
        if weight_col is not None and weight_col < len(row) and row[weight_col] is not None:
            try:
                weight = float(row[weight_col])
            except ValueError:
                weight = None
        members[symbol] = {"name": name, "weight_pct": weight}
    return {"as_of": as_of, "source": url, "members": members, "complete": True}


def fetch_qqq() -> dict:
    url = "https://api.nasdaq.com/api/quote/list-type/nasdaq100"
    response = httpx.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    response.raise_for_status()
    payload = response.json()
    rows = payload["data"]["data"]["rows"]
    as_of = payload["data"]["date"]
    total_cap = 0.0
    parsed = []
    for row in rows:
        symbol = _normalize_ticker(row.get("symbol") or "")
        cap_raw = (row.get("marketCap") or "").replace(",", "")
        cap = float(cap_raw) if cap_raw.replace(".", "", 1).isdigit() else None
        if symbol:
            parsed.append((symbol, row.get("companyName", ""), cap))
            if cap:
                total_cap += cap
    members = {
        symbol: {"name": name, "weight_pct": round(cap / total_cap * 100, 4) if cap and total_cap else None}
        for symbol, name, cap in parsed
    }
    return {"as_of": as_of, "source": url, "members": members, "complete": True}


def fetch_stockanalysis_holdings(ticker: str) -> dict:
    url = f"https://stockanalysis.com/etf/{ticker.lower()}/holdings/"
    response = httpx.get(url, timeout=20, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    text = response.text
    # Real, server-rendered rows: <a href="/stocks/xxx/" >SYM</a> ... <td ...>Name</td> ... <td ...>NN.NN%</td>
    row_pattern = re.compile(
        r'<a href="/stocks/[a-z0-9.-]+/" >([A-Z.]+)</a>.*?class="shr[^"]*">([^<]+)</td>.*?<td class="[^"]*">([\d.]+)%</td>',
        re.DOTALL,
    )
    members: dict[str, dict] = {}
    for raw_symbol, name, weight in row_pattern.findall(text):
        symbol = _normalize_ticker(raw_symbol)
        if symbol is None:
            continue
        members[symbol] = {"name": name.strip(), "weight_pct": float(weight)}
    # Real, verified limitation (checked directly, not assumed): this free
    # page server-renders only the top 25 holdings by weight, not the fund's
    # full real membership (SOXX/IGV both real-hold closer to 30 names).
    # Disclosed in anchor_sources rather than silently presented as complete.
    complete = len(members) < 25
    return {"as_of": FROZEN_AT, "source": url, "members": members, "complete": complete}


def main() -> None:
    anchors: dict[str, dict] = {}
    for ticker in list(SSGA_INDEX_ANCHORS) + list(SSGA_SECTOR_ANCHORS):
        anchors[ticker] = fetch_ssga(ticker)
        print(f"{ticker}: {len(anchors[ticker]['members'])} real members (SSGA), as of {anchors[ticker]['as_of']}")
    anchors["QQQ"] = fetch_qqq()
    print(f"QQQ: {len(anchors['QQQ']['members'])} real members (Nasdaq API), as of {anchors['QQQ']['as_of']}")
    for ticker in STOCKANALYSIS_ANCHORS:
        anchors[ticker] = fetch_stockanalysis_holdings(ticker)
        print(f"{ticker}: {len(anchors[ticker]['members'])} real members (stockanalysis.com, issuer-disclosed weights), as of {anchors[ticker]['as_of']}")

    anchor_kind = {**SSGA_INDEX_ANCHORS, **SSGA_SECTOR_ANCHORS, "QQQ": "index", **STOCKANALYSIS_ANCHORS}

    all_symbols: dict[str, dict] = {}
    for anchor, info in anchors.items():
        for symbol, detail in info["members"].items():
            entry = all_symbols.setdefault(symbol, {"name": detail["name"], "memberships": []})
            entry["memberships"].append({
                "anchor": anchor,
                "anchor_kind": anchor_kind[anchor],
                "weight_pct": detail["weight_pct"],
            })

    print(f"\nTotal deduplicated symbols across all anchors: {len(all_symbols)}")
    index_only = sum(1 for e in all_symbols.values() if all(m["anchor_kind"] == "index" for m in e["memberships"]))
    thematic_only = sum(1 for e in all_symbols.values() if all(m["anchor_kind"] == "thematic_etf" for m in e["memberships"]))
    both = len(all_symbols) - index_only - thematic_only
    print(f"  index-only: {index_only}, thematic-only: {thematic_only}, both: {both}")

    draft = {
        "stage": STAGE,
        "frozen_at": FROZEN_AT,
        "compiled_at": datetime.now(timezone.utc).isoformat(),
        "method": (
            "SPY/DIA/XL-sector: State Street official holdings files. QQQ: Nasdaq official "
            "list-type API (weight derived from disclosed marketCap). SOXX/IGV: iShares' own "
            "disclosed weights, read via stockanalysis.com since iShares' own site blocks "
            "direct fetches -- one step removed from the issuer, disclosed as such."
        ),
        "immutability": "Frozen once written -- not re-generated in place. A future stage's universe gets a new, separately-named file.",
        "anchor_sources": {
            anchor: {
                "as_of": info["as_of"], "source": info["source"], "anchor_kind": anchor_kind[anchor],
                "count": len(info["members"]), "complete": info["complete"],
            }
            for anchor, info in anchors.items()
        },
        "total_unique_symbols": len(all_symbols),
        "symbols": [
            {"symbol": symbol, "name": entry["name"], "memberships": sorted(entry["memberships"], key=lambda m: m["anchor"])}
            for symbol, entry in sorted(all_symbols.items())
        ],
    }
    out_path = "/Users/rockychen/works/my-apps/Hierarchical-Exposure-Allocation-Engine-V1/backend/universe/stage-2-2026-08-27.json"
    with open(out_path, "w") as handle:
        json.dump(draft, handle, indent=2)
    print(f"\nFrozen file written to {out_path}")


if __name__ == "__main__":
    main()
