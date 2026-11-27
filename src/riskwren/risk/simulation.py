"""A simulation of annual loss from estimates in ranges (RSK-19).

Each estimate says how often a year (frequency) and how much each time (loss), each as a
low, likely, and high value. The simulation plays out many years. In each, for each estimate,
the year's rate is drawn from a PERT distribution over the frequency range, the number of
events from a Poisson distribution with that rate, and each event's loss from a PERT
distribution over the loss range; the year's loss is the sum. The estimates are taken to be
independent of one another.

The draws come from a generator seeded from what is simulated, so the same estimates always
give the same figures, and a report that quotes them can be checked. Every assumption is
returned with the figures, in words.
"""

from __future__ import annotations

import hashlib
import math
import random
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

YEARS = 10_000
PERCENTILES = (10, 50, 90, 95, 99)


@dataclass(frozen=True)
class Range:
    low: float
    likely: float
    high: float

    @property
    def mean(self) -> float:
        """The PERT mean: (low + 4 * likely + high) / 6."""
        return (self.low + 4 * self.likely + self.high) / 6


@dataclass(frozen=True)
class Inputs:
    label: str
    frequency: Range
    loss: Range


def pert(rng: random.Random, value: Range) -> float:
    if value.high <= value.low:
        return value.low
    span = value.high - value.low
    alpha = 1 + 4 * (value.likely - value.low) / span
    beta = 1 + 4 * (value.high - value.likely) / span
    return value.low + rng.betavariate(alpha, beta) * span


def poisson(rng: random.Random, rate: float) -> int:
    if rate <= 0:
        return 0
    if rate > 50:  # a normal approximation where counting one by one would be slow
        return max(0, round(rng.gauss(rate, math.sqrt(rate))))
    limit, count, product = math.exp(-rate), 0, rng.random()
    while product > limit:
        count += 1
        product *= rng.random()
    return count


def seed_of(inputs: Sequence[Inputs]) -> int:
    text = "|".join(
        f"{each.label}:{each.frequency}:{each.loss}"
        for each in sorted(inputs, key=lambda i: i.label)
    )
    return int(hashlib.sha256(text.encode()).hexdigest()[:16], 16)


def _percentile(ordered: list[float], share: float) -> float:
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, max(0, math.ceil(share / 100 * len(ordered)) - 1))
    return ordered[index]


def run(inputs: Sequence[Inputs], *, years: int = YEARS) -> dict[str, Any]:
    """Play out the years and say what they came to."""
    rng = random.Random(seed_of(inputs))  # noqa: S311  a simulation, not a secret
    totals: list[float] = []
    for _ in range(years):
        year = 0.0
        for each in inputs:
            for _ in range(poisson(rng, pert(rng, each.frequency))):
                year += pert(rng, each.loss)
        totals.append(year)
    ordered = sorted(totals)
    mean = sum(totals) / years if years else 0.0
    top = ordered[-1] if ordered else 0.0
    # Where the chance of a year's loss exceeding a figure is read off: ten round figures from
    # what one year in ten of those with any loss stays under, to the worst year simulated.
    positive = [total for total in ordered if total > 0]
    points = []
    if positive:
        start = max(positive[len(positive) // 10], 1.0)
        for step in range(10):
            figure = _round(start * (top / start) ** (step / 9)) if top > start else start
            if points and figure <= points[-1]["loss"]:
                continue
            beyond = len(ordered) - _bisect(ordered, figure)
            points.append({"loss": figure, "chance": round(beyond / years, 4)})
    return {
        "years": years,
        "seed": seed_of(inputs),
        "expected": round(sum(each.frequency.mean * each.loss.mean for each in inputs)),
        "mean": round(mean),
        "percentiles": {str(p): round(_percentile(ordered, p)) for p in PERCENTILES},
        "worst": round(top),
        "any_loss": round(sum(1 for total in totals if total > 0) / years, 4) if years else 0,
        "exceedance": points,
        "assumptions": [
            f"{years:,} simulated years, the same each time for the same estimates.",
            "How often a year, and the loss each time, each follow a PERT distribution over "
            "the low, likely, and high values given.",
            "The number of events in a year follows a Poisson distribution at that year's rate.",
            "Losses from separate events, and from separate risks, are independent.",
        ],
    }


def _round(value: float) -> int:
    """A figure to two significant digits, as people say them: 1,234,567 is 1,200,000."""
    if value < 10:
        return round(value)
    scale = 10 ** (int(math.log10(value)) - 1)
    return int(round(value / scale) * scale)


def _bisect(ordered: list[float], figure: float) -> int:
    """How many simulated years lost no more than the figure."""
    low, high = 0, len(ordered)
    while low < high:
        middle = (low + high) // 2
        if ordered[middle] <= figure:
            low = middle + 1
        else:
            high = middle
    return low
