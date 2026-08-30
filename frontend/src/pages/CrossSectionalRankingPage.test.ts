import { describe, expect, it } from "vitest";
import type { CrossSectionalRankingRow } from "../types";
import { compareRows, screenMatches } from "./CrossSectionalRankingPage";

function row(overrides: Partial<CrossSectionalRankingRow>): CrossSectionalRankingRow {
  return {
    symbol: "TEST", name: "Test", category: "stock", as_of: "2026-08-27", price: 100,
    score: 50, technical_context_score: 50, rs_3m: 0, rs_6m: 0, rs_12m: 0,
    high_52w_distance: 0, trend_distance: 0, slope: 0, above_all_mas: false, ordered_mas: false,
    median_dollar_volume_21d: 1_000_000, liquidity_rank: null, is_liquid_top100: false,
    rs_3m_percentile: null, is_current_leader: false, leadership_appearances_13w: 0,
    leadership_persistence: 0, candidate_weight: 0, return_5d: null,
    reversal_5d_percentile: null, sector_relative_return_5d: null,
    sector_relative_reversal_percentile: null, is_reversal_watch: false,
    ...overrides,
  };
}

describe("cross-sectional evidence presentation", () => {
  it("keeps evidence, sleeve, and legacy technical screens distinct", () => {
    const liquid = row({ is_liquid_top100: true });
    const sleeve = row({ candidate_weight: 0.05 });
    const aligned = row({ above_all_mas: true });

    expect(screenMatches(liquid, "liquid")).toBe(true);
    expect(screenMatches(sleeve, "portfolio")).toBe(true);
    expect(screenMatches(aligned, "aligned")).toBe(true);
    expect(screenMatches(liquid, "portfolio")).toBe(false);
  });

  it("sorts leadership by persistence, then current 3M percentile", () => {
    const rows = [
      row({ symbol: "LOW", leadership_persistence: 0.5, rs_3m_percentile: 90 }),
      row({ symbol: "TIE2", leadership_persistence: 0.8, rs_3m_percentile: 70 }),
      row({ symbol: "TIE1", leadership_persistence: 0.8, rs_3m_percentile: 95 }),
    ];

    expect(rows.sort((a, b) => compareRows(a, b, "leadership_persistence")).map((item) => item.symbol))
      .toEqual(["TIE1", "TIE2", "LOW"]);
  });
});
