from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

import pytest

from backend.universe import compile_stage2_universe as compiler


class _StubResponse:
    def __init__(self, *, content: bytes = b"", payload: Any = None) -> None:
        self.content = content
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        return self._payload


def _mock_http_get(
    monkeypatch: pytest.MonkeyPatch,
    *,
    expected_url: str,
    response: _StubResponse,
) -> None:
    def fake_get(url: str, **_: Any) -> _StubResponse:
        assert url == expected_url
        return response

    monkeypatch.setattr(compiler.httpx, "get", fake_get)


def _inline_cell(reference: str, value: str) -> str:
    return (
        f'<c r="{reference}" t="inlineStr"><is><t>{value}</t></is></c>'
    )


def _number_cell(reference: str, value: str) -> str:
    return f'<c r="{reference}"><v>{value}</v></c>'


def _ssga_xlsx_fixture() -> bytes:
    workbook_xml = """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Holdings" sheetId="1" r:id="rId1"/></sheets>
</workbook>"""
    relationships_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
    Target="worksheets/holdings.xml"/>
</Relationships>"""
    worksheet_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1">{_inline_cell("B1", "As of 26-Aug-2026")}</row>
    <row r="3">{_inline_cell("A3", "Name")}{_inline_cell("B3", "Ticker")}{_inline_cell("E3", "Weight")}</row>
    <row r="4">{_inline_cell("A4", "Berkshire Hathaway")}{_inline_cell("B4", "BRK.B")}{_number_cell("E4", "5.5")}</row>
    <row r="5">{_inline_cell("A5", "DOLLAR GENERAL CORP")}{_inline_cell("B5", "DG")}{_number_cell("E5", "0.2")}</row>
    <row r="6">{_inline_cell("A6", "CONTRA EXAMPLE INC")}{_inline_cell("B6", "123CVR")}{_number_cell("E6", "0.0")}</row>
    <row r="7">{_inline_cell("A7", "US DOLLAR")}{_inline_cell("B7", "-")}{_number_cell("E7", "0.1")}</row>
    <row r="8"></row>
    <row r="9">{_inline_cell("A9", "Past performance is not a reliable indicator")}</row>
  </sheetData>
</worksheet>"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as workbook:
        workbook.writestr("xl/workbook.xml", workbook_xml)
        workbook.writestr("xl/_rels/workbook.xml.rels", relationships_xml)
        # Deliberately not sheet1.xml: the compiler must follow workbook rels.
        workbook.writestr("xl/worksheets/holdings.xml", worksheet_xml)
    return buffer.getvalue()


def test_ishares_csv_uses_full_official_rows_and_excludes_non_equities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = compiler.ISHARES_ANCHORS["SOXX"]
    fixture = """iShares Semiconductor ETF
Fund Holdings as of,"Aug 27, 2026"
Ticker,Name,Sector,Asset Class,Market Value,Weight (%)
NVDA,NVIDIA,Information Technology,Equity,1000,8.25
BRK.B,Berkshire Hathaway,Financials,Equity,500,4.00
IXTU6,E-mini Technology Future,Other,Futures,10,0.10
USD,US Dollar,Other,Cash,5,0.05
""".encode("utf-8")
    _mock_http_get(
        monkeypatch,
        expected_url=url,
        response=_StubResponse(content=fixture),
    )

    result = compiler.fetch_ishares("SOXX")

    assert result["as_of"] == "2026-08-27"
    assert result["source_row_count"] == 4
    assert result["eligible_row_count"] == 2
    assert result["mapped_member_count"] == 2
    assert result["excluded_row_count"] == 2
    assert result["rejected_row_count"] == 0
    assert result["source_roster_complete"] is True
    assert result["price_symbol_mapping_complete"] is True
    assert set(result["members"]) == {"NVDA", "BRK-B"}
    assert {row["source_identifier"] for row in result["excluded_rows"]} == {
        "IXTU6",
        "USD",
    }


def test_ark_csv_separates_full_roster_from_mapping_and_retains_audit_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = compiler.ARK_ANCHORS["ARKX"]
    fixture = """date,fund,company,ticker,cusip,shares,market value ($),weight (%)
08/28/2026,ARKX,ROCKET LAB,RKLB UQ,773121108,10,100,5.10%
08/28/2026,ARKX,KOMATSU LTD,6301,6496584,10,90,4.00%
08/28/2026,ARKX,SPACE EXPLORATION TECHN-CL A,SPCX,84615Q103,10,80,3.00%
08/28/2026,ARKX,GOLDMAN FS TRSY OBLIG INST 468,,X9USDGSFT,10,70,2.00%
08/28/2026,ARKX,UNMAPPED OVERSEAS,MYSTERY ZZ,ABC123,10,60,1.00%
""".encode("utf-8")
    _mock_http_get(
        monkeypatch,
        expected_url=url,
        response=_StubResponse(content=fixture),
    )

    result = compiler.fetch_ark()

    assert result["as_of"] == "2026-08-28"
    assert result["source_row_count"] == 5
    assert result["mapped_member_count"] == 2
    assert result["excluded_row_count"] == 2
    assert result["rejected_row_count"] == 1
    assert result["source_roster_complete"] is True
    assert result["price_symbol_mapping_complete"] is False
    assert result["complete_for_price_universe"] is False
    assert set(result["members"]) == {"RKLB", "6301.T"}
    assert {row["reason"] for row in result["excluded_rows"]} == {
        "private_security",
        "cash_or_cash_equivalent",
    }
    assert result["rejected_rows"][0]["source_identifier"] == "MYSTERY ZZ"
    assert result["rejected_rows"][0]["source_data"]["cusip"] == "ABC123"


def test_cross_source_thales_identity_maps_to_one_yahoo_symbol() -> None:
    assert compiler._map_price_symbol("ARKX", "HO") == "HO.PA"
    assert compiler._map_price_symbol("CIBR", "HO.FP") == "HO.PA"


def test_first_trust_html_validates_issuer_count_and_maps_local_identifiers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = compiler.FIRST_TRUST_ANCHORS["CIBR"]
    fixture = """
<html><body>
<div>Holdings of the Fund as of 8/27/2026</div>
<span>Total Number of Holdings (excluding cash): 2</span>
<table class="fundSilverGrid">
  <tr><td>Security Name</td><td>Identifier</td><td>CUSIP</td><td>Classification</td><td>Shares / Quantity</td><td>Market Value</td><td>Weighting</td></tr>
  <tr><td>Thales S.A.</td><td>HO.FP</td><td>F9156M108</td><td>Aerospace and Defense</td><td>10</td><td>$100</td><td>1.82%</td></tr>
  <tr><td>Palo Alto Networks</td><td>PANW</td><td>697435105</td><td>Software</td><td>20</td><td>$200</td><td>9.63%</td></tr>
  <tr><td>US Dollar</td><td>$USD</td><td>Other</td><td>Other</td><td>1</td><td>$1</td><td>0.01%</td></tr>
</table>
</body></html>
""".encode("utf-8")
    _mock_http_get(
        monkeypatch,
        expected_url=url,
        response=_StubResponse(content=fixture),
    )

    result = compiler.fetch_first_trust()

    assert result["as_of"] == "2026-08-27"
    assert result["source_reported_count"] == 2
    assert result["source_row_count"] == 3
    assert result["eligible_row_count"] == 2
    assert result["mapped_member_count"] == 2
    assert result["excluded_row_count"] == 1
    assert result["source_roster_complete"] is True
    assert result["price_symbol_mapping_complete"] is True
    assert set(result["members"]) == {"HO.PA", "PANW"}
    assert result["members"]["HO.PA"]["source_identifier"] == "HO.FP"


def test_ssga_reads_xlsx_from_memory_and_audits_every_source_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ticker = "SPY"
    expected_url = (
        "https://www.ssga.com/us/en/individual/etfs/library-content/products/"
        "fund-data/etfs/us/holdings-daily-us-en-spy.xlsx"
    )
    _mock_http_get(
        monkeypatch,
        expected_url=expected_url,
        response=_StubResponse(content=_ssga_xlsx_fixture()),
    )

    result = compiler.fetch_ssga(ticker)

    assert result["as_of"] == "2026-08-26"
    assert result["source_row_count"] == 4
    assert result["mapped_member_count"] == 2
    assert result["excluded_row_count"] == 2
    assert result["rejected_row_count"] == 0
    assert result["source_roster_complete"] is True
    assert result["price_symbol_mapping_complete"] is True
    assert result["members"]["BRK-B"]["weight_pct"] == 5.5
    assert "DG" in result["members"]
    assert {row["reason"] for row in result["excluded_rows"]} == {
        "contingent_value_right",
        "cash_or_currency",
    }


@pytest.mark.parametrize(
    ("name", "identifier", "reason"),
    [
        ("XAB MATERIALS SEP26", "IXDU6", "derivative_future"),
        ("POUND STERLING", "-", "cash_or_currency"),
        ("DOLLAR TREE INC", "DLTR", None),
    ],
)
def test_ssga_non_equity_exclusions_are_exact_not_name_substrings(
    name: str, identifier: str, reason: str | None
) -> None:
    assert compiler._ssga_exclusion_reason(name, identifier) == reason


def test_qqq_reports_source_and_mapping_counts_instead_of_claiming_both_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "https://api.nasdaq.com/api/quote/list-type/nasdaq100"
    payload = {
        "data": {
            "date": "Aug 27, 2026",
            "data": {
                "rows": [
                    {"symbol": "AAPL", "companyName": "Apple", "marketCap": "$2,000"},
                    {"symbol": "BRK.B", "companyName": "Berkshire", "marketCap": "1,000"},
                    {"symbol": "1234", "companyName": "Bad identifier", "marketCap": "500"},
                ]
            },
        }
    }
    _mock_http_get(
        monkeypatch,
        expected_url=url,
        response=_StubResponse(payload=payload),
    )

    result = compiler.fetch_qqq()

    assert result["as_of"] == "2026-08-27"
    assert result["source_row_count"] == 3
    assert result["mapped_member_count"] == 2
    assert result["rejected_row_count"] == 1
    assert result["source_roster_complete"] is True
    assert result["price_symbol_mapping_complete"] is False
    assert result["market_cap_value_count"] == 2
    assert result["market_cap_values_complete"] is True
    # An incomplete symbol mapping must not renormalize weights over a subset.
    assert all(member["weight_pct"] is None for member in result["members"].values())


def test_build_draft_keeps_dual_completeness_and_source_identifier() -> None:
    result = compiler._anchor_result(
        source="mock://soxx",
        source_kind="issuer_full_holdings_csv",
        source_declared_full=True,
        source_as_of_raw="Aug 27, 2026",
        source_row_count=1,
        members={
            "BRK-B": {
                "name": "Berkshire Hathaway",
                "weight_pct": 1.5,
                "source_identifier": "BRK.B",
            }
        },
        excluded_rows=[],
        rejected_rows=[],
    )

    draft = compiler.build_draft(
        {"SOXX": result}, compiled_at="2026-08-29T00:00:00+00:00"
    )

    metadata = draft["anchor_sources"]["SOXX"]
    assert metadata["source_roster_complete"] is True
    assert metadata["price_symbol_mapping_complete"] is True
    assert "complete" not in metadata
    membership = draft["symbols"][0]["memberships"][0]
    assert membership["source_identifier"] == "BRK.B"
    assert membership["anchor_kind"] == "thematic_etf"


def test_write_staging_universe_is_utf8_and_atomically_replaceable(tmp_path: Path) -> None:
    target = tmp_path / "stage-new.json"
    draft = {"name": "Atos – Paris", "symbol": "ATO.PA"}

    written = compiler.write_staging_universe(draft, target)

    assert written == target
    assert target.read_text(encoding="utf-8").endswith("\n")
    assert "Atos – Paris" in target.read_text(encoding="utf-8")
    assert json.loads(target.read_text(encoding="utf-8")) == draft

    compiler.write_staging_universe({"replacement": True}, target)
    assert json.loads(target.read_text(encoding="utf-8")) == {"replacement": True}
    assert not target.with_name(f".{target.name}.tmp").exists()
