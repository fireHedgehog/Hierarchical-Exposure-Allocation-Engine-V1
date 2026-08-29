# Staging Research V2

This is the active, disposable research workspace. It is a restart point, not a
paper library or runtime configuration system.

## Restart here

1. Open the README for the relevant research type.
2. Review its initial loop, frozen choices, and result-table shape.
3. Change the design freely while it is wrong or incomplete.
4. Run nothing until the design and dataset are manually approved.
5. Translate an accepted result into application code by hand.

Research reads data prepared by Admin Operations. It does not fetch provider
data, write to the application database, switch strategy versions, or dispatch
another experiment automatically.

Current checkpoint: H-XSEC-S2-001 completed on 2026-08-29, but the later
H-XSEC-S6-001 audit confirmed that its calendar-quarter and new-top-three rules
omit persistent leaders. The result retires that narrow design, not relative
strength. H-XSEC-S2-002 replaced it with a completed 15-factor monthly screen;
sector-neutral Amihud illiquidity is the one confirmed discovery relationship,
positive at 42/63 sessions in validation and holdout. H-XSEC-S5-001's rough
next-session long-only translation retained positive full/holdout excess through
50 bps assumed-cost stress, but real spread/impact and historical PIT membership
remain untested. It is a research candidate, not a registered production factor.
H-XSEC-S2-003 has now released Development only. Its fixed `20/50/100/200` loop
found no stock-selection candidate: continuous broad/within-sector ICs were
near zero or negative, and no E1/E5/EB20/ES transition passed the sector-excess,
persistent-control, drawdown, and curve-q gates together. Validation and
Holdout remain unopened. The correlated index ES panel is a useful observation
for a new timing design, not authority to translate or promote this Cross study.
H-THEME-S2-001 remains a diagnostic of the retired clock and authorizes no
broader Theme conclusion.

## Research types

| Type | Question |
| --- | --- |
| [Macro](macro/README.md) | What macro-financial state exists, what follows it, and how much total risk should it eventually permit? |
| [Cross-Sectional](cross-sectional/README.md) | When does a security emerge as or remain a leader, and what follows on an event-time clock? |
| [Timing](timing/README.md) | When should an already-selected candidate be entered, held, trimmed, or exited? |
| [Theme](theme/README.md) | Does group participation add information after an individual leader is already observable? |

Add another type only when its experiment genuinely cannot fit one of these.
Do not create empty folders in anticipation.

## Study roles

| Code | Role | Allowed claim |
| --- | --- | --- |
| S1 | State Description | What is observable now |
| S2 | Predictive Relationship | What tends to follow or covary with it |
| S3 | Risk Probability | How often a defined event follows |
| S4 | Decision Policy | What action consumes an accepted state or probability |
| S5 | Trading Implementation | Whether an action survives real implementation constraints |
| S6 | Structural Diagnosis | Whether inputs are redundant, unstable, or misdefined |
| S7 | Human Observation | A dated qualitative observation before structured evidence exists |

One file may loop many signals, targets, and horizons when they share one method
and one primary role. Do not create one paper per p-value. Keep S2, S3, and S4
separate when a relationship is translated into a probability or policy.

## Naming and minimal header

Use `H-<TYPE>-S<ROLE>-<NNN>` and a lowercase filename. Type codes are `MACRO`,
`XSEC`, `TIME`, and `THEME`.

```markdown
# H-<TYPE>-S<ROLE>-<NNN> - <Role> - <Title>

| Field | Value |
| --- | --- |
| Study ID | H-<TYPE>-S<ROLE>-<NNN> |
| Legacy ID | None |
| Status | Design / Preregistered / Running / Confirmed / Rejected / Inconclusive |
| Dataset | Exact local dataset |
| Input | Exact observable input |
| Target | Exact measured outcome |
| Production use | None, unless manually accepted later |
| Does not claim | Nearest tempting overclaim |
```

The type README may hold its first matrix design. Create another file only when
an independent result or observation log needs its own lifecycle.

## Working rules

- Prefer one ranked result table to repeated prose.
- Show effect size, sample size, and stability. Show raw p-value and adjusted
  q-value only when the frozen design actually declares an inferential family;
  do not manufacture them for a fold-and-comparison design.
- A low p-value is not a business decision.
- Preserve nulls and failed results.
- No hashes, approval chains, or research-specific SQL schema are required.
- Git is sufficient history for disposable work.
- A running staging algorithm may remain naive or wrong; research labels it
  honestly without disabling the application.

Prior experiments remain under [Staging V1](../archive/staging_1/README.md) only
as temporary code and result context. Do not expand that archive.
