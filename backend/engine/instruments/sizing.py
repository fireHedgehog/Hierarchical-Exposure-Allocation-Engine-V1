from __future__ import annotations

import math


def position_size(
    *,
    conviction: float,
    max_loss_per_unit: float,
    notional_budget: float,
    risk_per_position_fraction: float,
    unit_multiplier: float = 1.0,
) -> tuple[int, float]:
    """Returns (quantity, risk_dollars_allocated).

    Risk budget scales linearly with |conviction| (0..5), capped at
    risk_per_position_fraction of notional_budget at conviction 5. Quantity
    is floor(risk_budget / max_loss_per_unit) — never rounds up, so the
    realized max loss never exceeds the allocated risk budget. A quantity of
    0 is a real, honest answer (position too small to size within the risk
    cap), not an error.

    notional_budget and risk_per_position_fraction are the caller's
    responsibility to supply — this project keeps them in the database
    (`staging_budget_config`), not as a hardcoded constant here, so a
    downloaded clone and a running instance always show the same
    inspectable, editable default rather than a value buried in source.
    """

    risk_budget = notional_budget * risk_per_position_fraction * (min(abs(conviction), 5.0) / 5.0)
    if max_loss_per_unit <= 0:
        return 0, 0.0
    per_unit_dollars = max_loss_per_unit * unit_multiplier
    quantity = math.floor(risk_budget / per_unit_dollars)
    return quantity, quantity * per_unit_dollars
